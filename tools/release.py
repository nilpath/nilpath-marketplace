"""Plan component releases, prepare proposals, and reconcile GitHub drafts.

GitHub operations use only the standard library and execute no candidate code.
Renderer and YAML imports belong only to local planning operations.
"""

from __future__ import annotations

import argparse
import ast
import base64
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import tomllib
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parent / "buildkit/src"))
from buildkit.ownership import REGISTRIES, owns, snapshot as generated_snapshot


CLIFF_VERSION = "2.13.1"
BOUNDARY = b"<!-- release-legacy-boundary -->\n"
PREFIX = (
    b"# Changelog\n\n"
    b"Component release notes are generated above the legacy boundary.\n\n"
    b"## Legacy changelog\n\n"
    b"The unchanged historical notes below, including Unreleased, are not generator input.\n\n"
    + BOUNDARY + b"\n"
)
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")
BUMPS = {"none": 0, "patch": 1, "minor": 2, "major": 3, "initial": 4}
PROPOSAL_MARKER = "<!-- nilpath-release-proposal:"
COMPLETION_MARKER = "<!-- nilpath-release-complete:"
BOT = "github-actions[bot]"
BOT_ID = 41898282
ACTIONS_APP_ID = 15368


class ReleaseError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReleaseError(message)


def fields(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected), f"Invalid fields, expected {expected}")


def text(value, pattern=None):
    require(isinstance(value, str) and bool(value.strip()), "Expected nonempty text")
    if pattern:
        require(pattern.fullmatch(value) is not None, f"Invalid value {value!r}")
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def load_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON field {key}")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique)
    except (ValueError, UnicodeError) as exc:
        raise ReleaseError(f"Invalid JSON: {exc}") from exc


def safe_path(value):
    text(value)
    path = PurePosixPath(value)
    require(not path.is_absolute() and str(path) == value, "Noncanonical artifact path")
    require(bool(path.parts) and not re.match(r"[A-Za-z]:", value), "Unsafe artifact path")
    require(all(p not in {".", "..", ".git"} for p in path.parts), "Unsafe artifact path")
    require("\\" not in value and not any(ord(c) < 32 for c in value), "Unsafe artifact path")
    return value


@dataclass(frozen=True)
class Decision:
    component: str
    commit: str
    bump: str
    reason: str


@dataclass(frozen=True)
class Component:
    name: str
    source: str
    version: str
    baseline: str | None


@dataclass(frozen=True)
class NoChanges:
    explanations: tuple[str, ...]


@dataclass(frozen=True)
class NeedsDecisions:
    plan: dict


@dataclass(frozen=True)
class ReadyPlan:
    plan: dict


def decisions_from_data(data):
    require(isinstance(data, list), "Decisions must be a list")
    result = []
    seen = set()
    for row in data:
        fields(row, ("component", "commit", "bump", "reason"))
        text(row["component"], NAME)
        text(row["commit"], SHA)
        require(row["bump"] in BUMPS, "Unknown bump")
        text(row["reason"])
        key = (row["component"], row["commit"])
        require(key not in seen, "Duplicate component/commit decision")
        seen.add(key)
        result.append(Decision(**row))
    return tuple(sorted(result, key=lambda d: (d.component, d.commit)))


def read_decisions(raw):
    data = tomllib.loads(raw.decode())
    require(set(data) <= {"decision"}, "Unknown decision configuration")
    return decisions_from_data(data.get("decision", []))


def decisions_bytes(decisions):
    lines = ["# Reviewed decisions. Exact component and commit identities are durable.\n"]
    for item in decisions:
        lines.append("\n[[decision]]\n")
        for key, value in asdict(item).items():
            lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}\n")
    return "".join(lines).encode()


def validate_plan(plan):
    require(isinstance(plan, dict), "Invalid plan")
    schema = plan.get("schema")
    require(type(schema) is int and schema in {1, 2}, "Unsupported plan schema")
    fields(plan, (
        "schema", "state", "input_sha", "proposal_date", "releases", "decisions",
        "requests", "explanations", "decisions_digest", "policy_digest", "tool_versions", "plan_id",
    ) + (("generated",) if schema == 2 else ()))
    require(plan["state"] in {"NeedsDecisions", "ReadyPlan"}, "Invalid transaction state")
    text(plan["input_sha"], SHA)
    require(date.fromisoformat(plan["proposal_date"]).isoformat() == plan["proposal_date"], "Invalid date")
    decisions = decisions_from_data(plan["decisions"])
    require(digest(canonical(plan["decisions"])) == plan["decisions_digest"], "Decision digest mismatch")
    text(plan["policy_digest"], DIGEST)
    fields(plan["tool_versions"], ("git-cliff", "policy"))
    text(plan["tool_versions"]["git-cliff"], VERSION)
    text(plan["tool_versions"]["policy"], re.compile(r"[1-9]\d*\Z"))
    require(isinstance(plan["explanations"], list), "Invalid explanations")
    for explanation in plan["explanations"]:
        text(explanation)
    require(isinstance(plan["requests"], list), "Invalid requests")
    for request in plan["requests"]:
        fields(request, ("component", "commit", "suggestion", "reason"))
        text(request["component"], NAME)
        text(request["commit"], SHA)
        require(request["suggestion"] in BUMPS, "Invalid suggestion")
        text(request["reason"])
    require(isinstance(plan["releases"], list), "Invalid releases")
    seen = set()
    for release in plan["releases"]:
        fields(release, ("component", "source", "baseline", "current", "target", "commits", "notes", "notes_sha256"))
        name = text(release["component"], NAME)
        require(name not in seen, "Duplicate release component")
        seen.add(name)
        source = safe_path(release["source"])
        require(source in {f"src/plugins/{name}/plugin.yaml", "src/marketplace.yaml"}, "Invalid component source")
        if release["baseline"] is not None:
            text(release["baseline"], SHA)
        text(release["current"], VERSION)
        text(release["target"], VERSION)
        current = tuple(map(int, release["current"].split(".")))
        target = tuple(map(int, release["target"].split(".")))
        require(target > current or target == current and release["baseline"] is None, "Non-increasing release version")
        require(isinstance(release["commits"], list) and release["commits"], "Empty release")
        require(len(set(release["commits"])) == len(release["commits"]), "Duplicate commit")
        for sha in release["commits"]:
            text(sha, SHA)
        text(release["notes"])
        require(digest(release["notes"].encode()) == release["notes_sha256"], "Notes digest mismatch")
    if plan["state"] == "NeedsDecisions":
        require(plan["requests"] and not plan["releases"], "Blocked plans cannot apply partial bumps")
    else:
        require(not plan["requests"], "Ready plan has unanswered requests")
    if schema == 2:
        require(plan["tool_versions"]["policy"] == "2", "Unsupported historical policy, reviewed repair required")
        require(isinstance(plan["generated"], list), "Invalid generated operations")
        seen_paths = []
        for edit in plan["generated"]:
            fields(edit, ("op", "path", "mode", "sha256"))
            require(edit["op"] in {"put", "delete"}, "Invalid generated operation")
            path = safe_path(edit["path"])
            require(owns(path), "Generated operation outside build ownership")
            require(edit["mode"] in {"100644", "100755"}, "Unsafe generated mode")
            text(edit["sha256"], DIGEST)
            seen_paths.append(path)
        require(seen_paths == sorted(set(seen_paths)), "Noncanonical or duplicate generated operations")
        require(not plan["generated"] or plan["state"] == "ReadyPlan" and plan["releases"],
                "Only versioned releases may change generated output")
    identity = {key: value for key, value in plan.items() if key != "plan_id"}
    require(digest(canonical(identity)) == plan["plan_id"], "Plan identity mismatch")
    return decisions


def validate_current_plan(plan):
    validate_plan(plan)
    require(plan["tool_versions"] == {"git-cliff": CLIFF_VERSION, "policy": str(plan["schema"])},
            "Unsupported current tools")


def finish_plan(plan):
    plan.pop("plan_id", None)
    plan["decisions_digest"] = digest(canonical(plan["decisions"]))
    plan["plan_id"] = digest(canonical(plan))
    validate_current_plan(plan)
    return plan


def run(root, *args, input=None):
    proc = subprocess.run(args, cwd=root, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(proc.returncode == 0, f"{args[0]} failed: {proc.stderr.decode(errors='replace')}")
    return proc.stdout


def git(root, *args):
    return run(root, "git", "--no-pager", *args).decode().strip()


def blob(root, sha, path, optional=False):
    if optional and not git(root, "ls-tree", sha, "--", path):
        return None
    return run(root, "git", "show", f"{sha}:{path}")


def version_field(raw):
    matches = re.findall(rb"^version: ([0-9]+\.[0-9]+\.[0-9]+)\r?$", raw, re.M)
    require(len(matches) == 1, "Source must have exactly one top-level version field")
    version = matches[0].decode()
    text(version, VERSION)
    return version


def source_inventory(root):
    from buildkit.config import load_config
    require(not any(p.is_symlink() for p in (root / "src", *(root / "src").rglob("*"))),
            "Release sources cannot contain symlinks")
    cfg = load_config(root)
    baselines = tomllib.loads((root / ".release/baselines.toml").read_text())
    fields(baselines, ("baseline",))
    require(isinstance(baselines["baseline"], dict), "Invalid baselines")
    sources = [(p.name, p.src_dir.relative_to(root).as_posix() + "/plugin.yaml", p.version) for p in cfg.plugins]
    sources.append((cfg.marketplace["name"], "src/marketplace.yaml", cfg.marketplace["version"]))
    names = {name for name, _, _ in sources}
    require(set(baselines["baseline"]) <= names, "Removed component requires an explicit migration")
    components = []
    for name, source, version in sources:
        text(name, NAME)
        text(version, VERSION)
        require(source == "src/marketplace.yaml" or source == f"src/plugins/{name}/plugin.yaml", "Plugin name/path mismatch")
        anchor = baselines["baseline"].get(name)
        if anchor:
            text(anchor, SHA)
            require(git(root, "merge-base", "--is-ancestor", anchor, "HEAD") == "", "Baseline is not an ancestor")
        require(version_field((root / source).read_bytes()) == version, "Invalid source version")
        components.append(Component(name, source, version, anchor))
    return components, cfg


def previous_transactions(root):
    records = []
    for sha in git(root, "log", "--format=%H", "--", ".release/plan.json").splitlines():
        raw = blob(root, sha, ".release/plan.json", optional=True)
        require(raw is not None, "Prior transaction was removed")
        plan = load_json(raw)
        validate_plan(plan)
        require(plan["state"] == "ReadyPlan", "Incomplete prior release transaction")
        parents = git(root, "show", "-s", "--format=%P", sha).split()
        require(parents == [plan["input_sha"]], "Prior release has invalid input parent")
        for item in plan["releases"]:
            require(version_field(blob(root, sha, item["source"])) == item["target"], "Prior release source mismatch")
        records.append((sha, plan))
    return records


def bump_version(version, bump):
    major, minor, patch = map(int, version.split("."))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    require(bump == "patch", "Invalid arithmetic bump")
    return f"{major}.{minor}.{patch + 1}"


def policy_digest(originals):
    return digest(canonical({path: digest(originals[path]) for path in ("cliff.toml", "tools/release.py")}))


def check_current_versions(root, components, records):
    effective = {}
    for sha, plan in reversed(records):
        for item in plan["releases"]:
            effective[item["component"]] = item["target"]
    for component in components:
        expected = effective.get(component.name)
        if expected is None and component.baseline:
            expected = version_field(blob(root, component.baseline, component.source))
        require(expected is None or expected == component.version,
                f"Unexplained manual version change for {component.name}")


def changed_paths(root, sha):
    rows = git(root, "diff-tree", "--root", "--no-commit-id", "--name-status", "-r", "--no-renames", sha)
    return [tuple(line.split("\t", 1)) for line in rows.splitlines()]


def git_entries(root, sha):
    result = {}
    for row in run(root, "git", "ls-tree", "-rz", sha).split(b"\0"):
        if row:
            meta, path = row.decode().split("\t", 1)
            mode, kind, object_sha = meta.split()
            result[safe_path(path)] = (mode, kind, object_sha)
    return result


def committed_generated(root, sha):
    result = {}
    for path, (mode, kind, _) in git_entries(root, sha).items():
        if owns(path):
            require(kind == "blob" and mode in {"100644", "100755"}, f"Invalid generated file mode for {path}")
            result[path] = (mode, blob(root, sha, path))
    return result


def generated_delta(before, after):
    return [
        {"op": "put" if path in after else "delete", "path": path,
         "mode": (after if path in after else before)[path][0],
         "sha256": digest((after if path in after else before)[path][1])}
        for path in sorted(before.keys() | after.keys()) if before.get(path) != after.get(path)
    ]


def generated_components(before, after, cfg):
    affected = set()
    for path in before.keys() | after.keys():
        if before.get(path) == after.get(path):
            continue
        if path in REGISTRIES:
            old = load_json(before[path][1]) if path in before else {}
            new = load_json(after[path][1]) if path in after else {}
            old_plugins = {p["name"]: p for p in old.pop("plugins", [])}
            new_plugins = {p["name"]: p for p in new.pop("plugins", [])}
            changed_plugins = {name for name in old_plugins.keys() | new_plugins.keys()
                               if old_plugins.get(name) != new_plugins.get(name)}
            affected.update(changed_plugins)
            if old != new or not changed_plugins or path in before and path in after and before[path][0] != after[path][0]:
                affected.add(cfg.marketplace["name"])
            continue
        owners = [path.removeprefix(h.dist_root + "/plugins/").split("/")[0]
                  for h in cfg.harnesses.values() if path.startswith(h.dist_root + "/plugins/")]
        require(len(owners) == 1, f"No component owns generated path {path}")
        affected.add(owners[0])
    return affected


def pending_generated(root, cfg):
    from buildkit.build import build
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        build(root, out_root=out)
        return generated_components(committed_generated(root, "HEAD"), generated_snapshot(out), cfg)


def shipped_changed(root, sha, component, cfg):
    parents = git(root, "show", "-s", "--format=%P", sha).split()
    require(len(parents) == 1, "Shared attribution requires a linear commit")
    paths = [f"{h.dist_root}/plugins/{component}" for h in cfg.harnesses.values()]
    return bool(git(root, "diff", "--name-only", parents[0], sha, "--", *paths))


def cliff_context(root, commits, config):
    require(run(root, "git-cliff", "--version").decode().strip() == f"git-cliff {CLIFF_VERSION}", "Wrong git-cliff version")
    raw = run(root, "git-cliff", "--offline", "--no-exec", "--config", str(config),
              "--ignore-tags", ".*", "--context")
    context = load_json(raw)
    require(isinstance(context, list), "Invalid git-cliff context")
    parsed = {c["id"]: c for release in context for c in release["commits"]}
    require(set(commits) <= set(parsed), "git-cliff dropped commits")
    return parsed, context[0]


def render_notes(root, parsed, template, commits, label, config):
    notes_commits = [
        {**parsed[sha],
         "message": html.escape(parsed[sha]["message"].splitlines()[0], quote=False),
         "raw_message": html.escape(parsed[sha]["raw_message"].splitlines()[0], quote=False),
         "body": None, "footers": []}
        for sha in commits
    ]
    context = [{**template, "version": label, "commits": notes_commits,
                "previous": None}]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "context.json"
        path.write_bytes(canonical(context))
        notes = run(root, "git-cliff", "--offline", "--no-exec", "--config", str(config),
                    "--from-context", str(path), "--strip", "all").decode().strip() + "\n"
    require(notes.strip(), "git-cliff rendered empty notes")
    return notes


def propose(root, decisions=(), proposal_date=None):
    root = root.resolve()
    input_sha = git(root, "rev-parse", "HEAD")
    components, cfg = source_inventory(root)
    pending = pending_generated(root, cfg)
    records = previous_transactions(root)
    effective = {}
    for sha, plan in reversed(records):
        for item in plan["releases"]:
            effective[item["component"]] = (sha, item["target"])
    decisions_map = {(d.component, d.commit): d for d in decisions}
    accepted = read_decisions((root / ".release/decisions.toml").read_bytes())
    for item in accepted:
        require(decisions_map.get((item.component, item.commit)) == item, "Accepted decision removed or changed")
    candidates = {}
    explanations = []
    considered = set()
    for component in components:
        boundary, previous = effective.get(component.name, (component.baseline, None))
        if boundary:
            previous = previous or version_field(blob(root, boundary, component.source))
            require(previous == component.version, f"Unexplained manual version change for {component.name}")
            commits = git(root, "rev-list", "--reverse", f"{boundary}..{input_sha}").splitlines()
        else:
            authored = git(root, "rev-list", "--reverse", input_sha, "--", component.source).splitlines()
            require(authored, "New plugin has no authored introduction")
            introduced = authored[0]
            require(version_field(blob(root, introduced, component.source)) == component.version,
                    "Unexplained manual version change for new component")
            commits = [introduced] + git(root, "rev-list", "--reverse", f"{introduced}..{input_sha}").splitlines()
        for sha in commits:
            if any(sha == transaction_sha for transaction_sha, _ in records):
                continue
            considered.add(sha)
            paths = changed_paths(root, sha)
            direct = [(status, path) for status, path in paths if (
                path == component.source if component.source == "src/marketplace.yaml"
                else path.startswith(f"src/plugins/{component.name}/")
            )]
            shared = any(path.startswith(("src/harnesses/", "tools/buildkit/")) or path == "src/marketplace.yaml"
                         for _, path in paths)
            if direct and boundary and any(path == component.source for _, path in direct):
                parent = git(root, "show", "-s", "--format=%P", sha).split()[0]
                require(version_field(blob(root, parent, component.source)) ==
                        version_field(blob(root, sha, component.source)),
                        f"Unexplained manual source version change for {component.name} at {sha}")
            if component.source == "src/marketplace.yaml" and direct:
                parent = git(root, "show", "-s", "--format=%P", sha).split()[0]
                import yaml
                before = yaml.safe_load(blob(root, parent, component.source))
                after = yaml.safe_load(blob(root, sha, component.source))
                if {k: v for k, v in before.items() if k != "defaults"} == {k: v for k, v in after.items() if k != "defaults"}:
                    direct = []
            if not direct and shared:
                if component.name not in pending and (
                        component.source == "src/marketplace.yaml" or not shipped_changed(root, sha, component.name, cfg)):
                    explanations.append(f"{component.name}: {sha} shared change leaves shipped trees unchanged.")
                    continue
            elif not direct:
                continue
            new = boundary is None
            shared_effect = shared and not new and (component.name in pending or (
                component.source != "src/marketplace.yaml" and shipped_changed(root, sha, component.name, cfg)))
            candidates[(component.name, sha)] = (component, boundary, paths, direct, shared_effect, new)
        if component.name in pending and not any(name == component.name for name, _ in candidates):
            candidates[(component.name, input_sha)] = (
                component, boundary, changed_paths(root, input_sha), [], True, boundary is None)
    for sha in sorted(considered):
        if not any(path.startswith(("src/", "tools/buildkit/", "dist/")) or path in REGISTRIES
                   for _, path in changed_paths(root, sha)):
            explanations.append(f"{sha}: repository-only changes do not bump shipped components.")
    all_commits = list(dict.fromkeys(sha for _, sha in candidates))
    parsed, template = cliff_context(root, all_commits, root / "cliff.toml") if all_commits else ({}, None)
    requests = []
    selected = {}
    used = set()
    for (name, sha), (component, boundary, paths, direct, shared, new) in candidates.items():
        commit = parsed[sha]
        kind = ({"Added": "feat", "Fixed": "fix", "Changed": "docs"}.get(commit.get("group"))
                if commit.get("conventional") else None)
        scope = commit.get("scope")
        breaking = commit.get("breaking", False)
        added = any(status == "A" and re.search(r"/(skills/[^/]+/SKILL\.md\.j2|agents/[^/]+/[^/]+\.md\.j2)$", path)
                    for status, path in direct)
        removed = any(status == "D" for status, _ in direct)
        suggestion = "initial" if new else "major" if breaking else "minor" if kind == "feat" or added else "patch"
        reason = None
        if new:
            reason = f"Confirm authored initial version {component.version}."
        elif component.source == "src/marketplace.yaml":
            reason = "Marketplace release-bearing metadata requires its own severity decision."
        elif shared:
            reason = "Shared code changes shipped output. Decide severity for this component."
        elif removed:
            reason = "Removal requires compatibility review."
        elif scope and scope != name:
            reason = f"Commit scope {scope!r} conflicts with changed component."
        elif kind not in {"fix", "docs", "perf", "refactor", "feat"}:
            reason = "Unknown or nonconventional commit requires review."
        elif breaking and component.version.startswith("0."):
            reason = "Pre-1.0 breaking change requires review."
        elif suggestion == "minor" and component.version.startswith("0.0."):
            reason = "Feature on 0.0.x requires review."
        override = decisions_map.get((name, sha))
        if override:
            used.add((name, sha))
            require((override.bump == "initial") == new or override.bump == "none", "Initial decision only applies to new plugins")
            suggestion = override.bump
            explanations.append(f"{name}: {sha} reviewed {suggestion}. {override.reason}")
        elif reason:
            requests.append({"component": name, "commit": sha, "suggestion": suggestion, "reason": reason})
        else:
            explanations.append(f"{name}: {sha} suggests {suggestion} from direct conventional or added-component evidence.")
        if suggestion != "none":
            selected.setdefault(name, []).append((sha, suggestion, component, boundary))
    accepted_keys = {(d.component, d.commit) for d in accepted}
    require(set(decisions_map) <= used | accepted_keys, "Stale or unrelated resolution decision")
    for name in sorted(pending - selected.keys()):
        sha = next(sha for component, sha in reversed(candidates) if component == name)
        if not any(row["component"] == name for row in requests):
            requests.append({
                "component": name, "commit": sha, "suggestion": "patch",
                "reason": "Full regeneration changes this component without a release version. A bump is required.",
            })
    if not candidates:
        explanations.append("Repository-only changes do not bump shipped components.")
    if not requests and not selected and tuple(decisions) == accepted:
        return NoChanges(tuple(explanations))
    plan = {
        "schema": 2, "state": "NeedsDecisions" if requests else "ReadyPlan",
        "input_sha": input_sha, "proposal_date": proposal_date or git(root, "show", "-s", "--format=%cs", input_sha),
        "releases": [], "decisions": [asdict(d) for d in decisions], "requests": requests,
        "explanations": explanations, "policy_digest": policy_digest({
            p: (root / p).read_bytes() for p in ("cliff.toml", "tools/release.py")}),
        "tool_versions": {"git-cliff": CLIFF_VERSION, "policy": "2"}, "generated": [],
    }
    if not requests:
        for name, rows in sorted(selected.items()):
            component, boundary = rows[0][2:]
            bump = max((row[1] for row in rows), key=BUMPS.get)
            target = component.version if bump == "initial" else bump_version(component.version, bump)
            commits = [row[0] for row in rows]
            notes = render_notes(root, parsed, template, commits, f"{name}/v{target}", root / "cliff.toml")
            plan["releases"].append({
                "component": name, "source": component.source, "baseline": boundary,
                "current": component.version, "target": target, "commits": commits,
                "notes": notes, "notes_sha256": digest(notes.encode()),
            })
    finish_plan(plan)
    return NeedsDecisions(plan) if requests else ReadyPlan(plan)


def replace_version(raw, current, target):
    require(version_field(raw) == current, "Source version does not match plan")
    return re.sub(rb"(?m)^version: " + re.escape(current.encode()) + rb"$",
                  b"version: " + target.encode(), raw, count=1)


def readme_update(raw, name, current, target, root=False):
    pattern = (rb"(?m)^(\| \*\*" + re.escape(name.encode()) + rb"\*\* \| )(" + re.escape(current.encode()) + rb")( \|)"
               if root else rb"(?m)^(Version: \*\*)(" + re.escape(current.encode()) + rb")(\*\*)$")
    matches = list(re.finditer(pattern, raw))
    if root:
        require(len(matches) == 1, f"Missing or duplicate current README cell for {name}")
    else:
        require(len(matches) <= 1, "Duplicate README current-version header")
        if b"Version: **" in raw:
            require(len(matches) == 1, f"README current-version header mismatch for {name}")
    return re.sub(pattern, lambda m: m[1] + target.encode() + m[3], raw)


def schema1_changelog_update(raw, plan):
    require(raw.count(BOUNDARY) == 1, "Missing or duplicate legacy changelog boundary")
    if not plan["releases"]:
        return raw
    sections = []
    for item in plan["releases"]:
        sections.append(f"## [{item['component']} {item['target']}] - {plan['proposal_date']}\n\n{item['notes']}\n".encode())
    header = b"# Changelog\n\nComponent release notes are generated above the legacy boundary.\n\n"
    require(raw.startswith(header), "Missing changelog insertion point")
    return header + b"".join(sections) + raw[len(header):]


def changelog_update(raw, plan):
    return schema1_changelog_update(raw, plan)


def expected_updates(plan, originals, payload=None):
    """Derive the only files the writer is permitted to apply, without YAML."""
    validate_current_plan(plan)
    if plan["schema"] == 2:
        return _schema2_updates(plan, originals, payload or {})
    updates = _schema1_updates(plan, originals, changelog_update)
    require(updates == historical_updates(plan, originals),
            "Current generation violates schema-1 byte contract, reviewed schema repair required")
    return updates


def historical_updates(plan, originals, payload=None):
    """Verify recorded schema bytes without executing historical code."""
    validate_plan(plan)
    require(plan["tool_versions"]["policy"] == str(plan["schema"]),
            "Unsupported historical policy, reviewed repair required")
    try:
        source = ast.parse(originals["tools/release.py"])
    except (SyntaxError, ValueError) as exc:
        raise ReleaseError("Unsupported historical policy source, reviewed repair required") from exc
    pins = [node.value.value for node in source.body
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
            and any(isinstance(target, ast.Name) and target.id == "CLIFF_VERSION" for target in node.targets)]
    require(pins == [plan["tool_versions"]["git-cliff"]], "Historical tool identity mismatch")
    if plan["schema"] == 2:
        return _schema2_updates(plan, originals, payload or {})
    return _schema1_updates(plan, originals, schema1_changelog_update)


def _schema2_updates(plan, originals, payload):
    updates = _schema1_updates(plan, {p: b for p, b in originals.items() if not owns(p)}, schema1_changelog_update)
    for edit in plan["generated"]:
        path = edit["path"]
        if edit["op"] == "delete":
            require(path in originals and digest(originals[path]) == edit["sha256"],
                    f"Deletion input mismatch for {path}")
            updates[path] = None
        else:
            raw = payload.get(path)
            require(isinstance(raw, bytes) and digest(raw) == edit["sha256"], f"Generated payload mismatch for {path}")
            updates[path] = raw
    return updates


def update_modes(plan):
    return {edit["path"]: edit["mode"] for edit in plan.get("generated", [])}


def check_deletion_modes(plan, tree):
    for edit in plan.get("generated", []):
        if edit["op"] == "delete":
            require(tree.get(edit["path"], {}).get("mode") == edit["mode"], "Deletion input mode mismatch")


def _schema1_updates(plan, originals, render_changelog):
    require(policy_digest(originals) == plan["policy_digest"], "Plan policy digest mismatch")
    updates = {
        ".release/plan.json": canonical(plan) + b"\n",
        ".release/decisions.toml": decisions_bytes(decisions_from_data(plan["decisions"])),
    }
    if plan["state"] != "ReadyPlan":
        return {p: b for p, b in updates.items() if originals.get(p) != b}
    releases = {item["component"]: item for item in plan["releases"]}
    root_readme = originals.get("README.md", b"")
    for item in plan["releases"]:
        name, current, target = item["component"], item["current"], item["target"]
        source = item["source"]
        require(source in originals, f"Missing original {source}")
        require(re.findall(rb"(?m)^name: ([a-z0-9-]+)$", originals[source]) == [name.encode()],
                "Component source identity mismatch")
        updates[source] = replace_version(originals[source], current, target)
        if source != "src/marketplace.yaml":
            root_readme = readme_update(root_readme, name, current, target, root=True)
            source_readme = f"src/plugins/{name}/README.md"
            if source_readme in originals:
                updates[source_readme] = readme_update(originals[source_readme], name, current, target)
    if plan["releases"]:
        updates["README.md"] = root_readme
        updates["CHANGELOG.md"] = render_changelog(originals["CHANGELOG.md"], plan)
    for path, raw in originals.items():
        if path in REGISTRIES:
            data = load_json(raw)
            for entry in data["plugins"]:
                item = releases.get(entry["name"])
                if item and "version" in entry:
                    require(entry["version"] == item["current"], "Registry source version mismatch")
                    entry["version"] = item["target"]
            market = next((r for r in releases.values() if r["source"] == "src/marketplace.yaml"), None)
            if market and "metadata" in data:
                require(data["metadata"]["version"] == market["current"], "Marketplace version mismatch")
                data["metadata"]["version"] = market["target"]
            updates[path] = json.dumps(data, indent=2, ensure_ascii=False).encode() + b"\n"
        match = re.fullmatch(r"dist/(claude|copilot|codex)/plugins/([a-z0-9-]+)/(README\.md|\.claude-plugin/plugin\.json|plugin\.json|\.codex-plugin/plugin\.json)", path)
        if not match or match[2] not in releases:
            continue
        item = releases[match[2]]
        if match[3] == "README.md":
            updates[path] = readme_update(raw, item["component"], item["current"], item["target"])
        else:
            data = load_json(raw)
            require(data["name"] == item["component"] and data["version"] == item["current"], "Manifest identity mismatch")
            data["version"] = item["target"]
            updates[path] = json.dumps(data, indent=2, ensure_ascii=False).encode() + b"\n"
    return {path: raw for path, raw in updates.items() if originals.get(path) != raw}


def relevant_path(path, plan):
    if plan["schema"] == 2 and owns(path):
        return any(edit["path"] == path and edit["op"] == "delete" for edit in plan["generated"])
    if path in {"README.md", "CHANGELOG.md", ".release/plan.json", ".release/decisions.toml",
                "cliff.toml", "tools/release.py", *REGISTRIES}:
        return True
    for item in plan["releases"]:
        name = item["component"]
        if path in {item["source"], f"src/plugins/{name}/README.md"}:
            return True
        if re.fullmatch(rf"dist/(claude|copilot|codex)/plugins/{re.escape(name)}/(README\.md|\.claude-plugin/plugin\.json|plugin\.json|\.codex-plugin/plugin\.json)", path):
            return True
    return False


def tracked_originals(root, plan, sha):
    result = {}
    for path, (mode, kind, _) in git_entries(root, sha).items():
        if relevant_path(path, plan):
            allowed = {"100644", "100755"} if plan["schema"] == 2 and owns(path) else {"100644"}
            require(kind == "blob" and mode in allowed, f"Invalid release file mode for {path}")
            result[path] = blob(root, sha, path)
    return result


def prepare(root, plan):
    validate_current_plan(plan)
    require(git(root, "rev-parse", "HEAD") == plan["input_sha"], "Stale preparation input")
    originals = tracked_originals(root, plan, plan["input_sha"])
    if plan["schema"] == 2:
        plan["generated"] = []
        finish_plan(plan)
        updates = expected_updates(plan, originals)
        if plan["state"] == "ReadyPlan":
            from buildkit.build import build
            from buildkit.config import load_config
            import shutil
            with tempfile.TemporaryDirectory() as tmp:
                render_root = Path(tmp)
                shutil.copytree(root / "src", render_root / "src", symlinks=False)
                for path, raw in updates.items():
                    if path.startswith("src/"):
                        (render_root / path).write_bytes(raw)
                build(render_root)
                after = generated_snapshot(render_root)
            before = committed_generated(root, plan["input_sha"])
            changed = generated_components(before, after, load_config(root))
            selected = {item["component"] for item in plan["releases"]}
            require(changed <= selected, "Full regeneration changes components without a version bump: "
                    + ", ".join(sorted(changed - selected)))
            plan["generated"] = generated_delta(before, after)
            finish_plan(plan)
            originals.update({p: row[1] for p, row in before.items()})
            updates = expected_updates(plan, originals, {p: row[1] for p, row in after.items()})
    else:
        updates = expected_updates(plan, originals)
        updates = {p: b for p, b in updates.items() if not owns(p)}
    modes = update_modes(plan)
    deletions = {path for path, raw in updates.items() if raw is None}
    puts = updates.keys() - deletions
    blocking_dirs = set()
    for path, raw in updates.items():
        target = root / path
        require(not target.is_symlink() and target.parent.resolve().is_relative_to(root.resolve()),
                "Refusing symlink or path escape")
        if raw is None and not target.exists():
            continue
        for parent in target.parents:
            if parent == root:
                break
            require(not parent.is_symlink(), "Refusing symlink parent")
            require(not parent.is_file() or parent.relative_to(root).as_posix() in deletions,
                    f"File blocking prepared path {path}")
        if target.is_dir():
            children = list(target.rglob("*"))
            allowed = deletions if raw is not None else puts
            require(all(not child.is_symlink() and (
                child.is_dir() or child.relative_to(root).as_posix() in allowed) for child in children),
                f"Untracked content blocking prepared path {path}")
            if raw is not None:
                blocking_dirs.update(child for child in children if child.is_dir())
                blocking_dirs.add(target)
    for path in deletions:
        target = root / path
        if target.is_file():
            target.unlink()
    for directory in sorted(blocking_dirs, key=lambda p: len(p.parts), reverse=True):
        directory.rmdir()
    for path, raw in updates.items():
        if raw is not None:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            target.chmod(int(modes.get(path, "100644"), 8) & 0o777)


def validate_request(request):
    fields(request, ("schema", "kind", "repository", "run_id", "run_attempt", "dispatcher_sha",
                     "input_sha", "proposal_pr", "expected_head", "merged_sha", "decisions"))
    require(type(request["schema"]) is int and request["schema"] == 1
            and request["kind"] in {"proposal", "drafts"}, "Invalid request")
    text(request["repository"], re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z"))
    for key in ("run_id", "run_attempt"):
        text(request[key], re.compile(r"[1-9]\d*\Z"))
    for key in ("dispatcher_sha", "input_sha"):
        text(request[key], SHA)
    for key in ("expected_head", "merged_sha"):
        if request[key] is not None:
            text(request[key], SHA)
    require(request["proposal_pr"] is None or type(request["proposal_pr"]) is int and request["proposal_pr"] > 0, "Invalid PR")
    decisions_from_data(request["decisions"])
    if request["kind"] == "drafts":
        require(request["proposal_pr"] is not None and request["expected_head"] is not None
                and request["merged_sha"] == request["input_sha"] and not request["decisions"],
                "Invalid drafts request identity")
    else:
        require(request["merged_sha"] is None
                and (request["proposal_pr"] is None) == (request["expected_head"] is None),
                "Invalid proposal request identity")


def bundle(root, request):
    validate_request(request)
    plan_path = root / ".release/plan.json"
    plan = load_json(plan_path.read_bytes()) if plan_path.exists() else None
    if request["kind"] == "proposal" and plan and plan["input_sha"] != request["input_sha"]:
        plan = None
    files = []
    if request["kind"] == "drafts":
        require(plan is not None and plan["state"] == "ReadyPlan", "Invalid merged transaction")
        validate_plan(plan)
    elif plan:
        validate_plan(plan)
        originals = tracked_originals(root, plan, request["input_sha"])
        payload = {p: b for p, (_, b) in generated_snapshot(root).items()} if plan["schema"] == 2 else {}
        expected = expected_updates(plan, originals, payload)
        modes = update_modes(plan)
        for path, raw in expected.items():
            actual = root / path
            mode = modes.get(path, "100644")
            if raw is None:
                require((not actual.exists() or actual.is_dir()) and not actual.is_symlink(),
                        "Prepared deletion still exists")
                edit = next(e for e in plan["generated"] if e["path"] == path)
                files.append({**edit, "content": None})
                continue
            require(not actual.is_symlink() and actual.is_file()
                    and actual.parent.resolve().is_relative_to(root.resolve()), "Missing or unsafe prepared file")
            require(actual.read_bytes() == raw, f"Prepared content mismatch for {path}")
            require(("100755" if actual.stat().st_mode & 0o111 else "100644") == mode, "Prepared mode mismatch")
            row = {"path": path, "mode": mode, "content": base64.b64encode(raw).decode(), "sha256": digest(raw)}
            if plan["schema"] == 2:
                row["op"] = "put"
            files.append(row)
        modified = set(git(root, "diff", "--no-renames", "HEAD", "--name-only").splitlines())
        untracked = set(git(root, "ls-files", "--others", "--exclude-standard").splitlines())
        require(modified | untracked == set(expected), "Unexpected preparation changes")
    result = {"request": request, "plan": plan, "files": files}
    result["digest"] = digest(canonical(result))
    return result


def validate_artifact(artifact):
    fields(artifact, ("request", "plan", "files", "digest"))
    validate_request(artifact["request"])
    require(digest(canonical({k: v for k, v in artifact.items() if k != "digest"})) == artifact["digest"], "Artifact digest mismatch")
    if artifact["plan"] is not None:
        if artifact["request"]["kind"] == "proposal":
            validate_current_plan(artifact["plan"])
        else:
            validate_plan(artifact["plan"])
    require(isinstance(artifact["files"], list), "Invalid files")
    files = {}
    for row in artifact["files"]:
        schema2 = artifact["plan"] is not None and artifact["plan"]["schema"] == 2
        fields(row, ("path", "mode", "content", "sha256") + (("op",) if schema2 else ()))
        path = safe_path(row["path"])
        allowed = {"100644", "100755"} if schema2 and owns(path) else {"100644"}
        require(path not in files and row["mode"] in allowed, "Duplicate path or unsafe mode")
        if schema2:
            require(row["op"] in {"put", "delete"}, "Invalid file operation")
            if owns(path):
                edit = next((e for e in artifact["plan"]["generated"] if e["path"] == path), None)
                require(edit == {k: v for k, v in row.items() if k != "content"},
                        "Generated file operation differs from plan")
            else:
                require(row["op"] == "put", "Only build-owned paths may be deleted")
            if row["op"] == "delete":
                require(row["content"] is None and owns(path), "Invalid deletion")
                text(row["sha256"], DIGEST)
                files[path] = None
                continue
        require(isinstance(row["content"], str), "Invalid file content")
        try:
            raw = base64.b64decode(row["content"], validate=True)
        except ValueError as exc:
            raise ReleaseError("Invalid base64") from exc
        require(len(raw) <= 2_000_000 and digest(raw) == row["sha256"], "Invalid file digest or size")
        files[path] = raw
    require(artifact["plan"] is not None or not files, "NoChanges has files")
    if artifact["request"]["kind"] == "drafts":
        require(not files and artifact["plan"] is not None, "Invalid drafts artifact")
    return files


def reconstruct(root, input_sha, decisions):
    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "input"
        run(root, "git", "-c", "core.hooksPath=/dev/null", "clone", "--quiet",
            "--no-local", "--no-checkout", str(root), str(clean))
        git(clean, "-c", "core.hooksPath=/dev/null", "checkout", "--quiet", "--detach", input_sha)
        result = propose(clean, decisions)
        if isinstance(result, NoChanges):
            return None
        prepare(clean, result.plan)
        originals = tracked_originals(clean, result.plan, input_sha)
        payload = {p: b for p, (_, b) in generated_snapshot(clean).items()}
        return result.plan, expected_updates(result.plan, originals, payload)


def renderer_identity(root=None, sha=None):
    root = root or Path(__file__).resolve().parent.parent
    files = git_entries(root, sha) if sha else (
        p.relative_to(root).as_posix() for p in (root / "tools/buildkit/src/buildkit").rglob("*.py"))
    paths = {"tools/release.py", "cliff.toml", "pyproject.toml", "uv.lock", "tools/buildkit/pyproject.toml"}
    paths.update(p for p in files if p.startswith("tools/buildkit/src/buildkit/")
                 and p.endswith(".py") and "__pycache__" not in PurePosixPath(p).parts)
    return digest(canonical({p: digest(blob(root, sha, p) if sha else (root / p).read_bytes()) for p in sorted(paths)}))


def verify_bundle(root, request, artifact):
    validate_request(request)
    validate_artifact(artifact)
    require(artifact["request"] == request, "Artifact snapshot is stale or mismatched")
    require(git(root, "rev-parse", "HEAD") == request["input_sha"], "Verifier checkout differs from immutable input")
    if request["kind"] == "proposal":
        require(renderer_identity(root, request["input_sha"]) == renderer_identity(),
                "Input and dispatcher renderer identities differ. Start a fresh dispatch.")
        reconstructed = reconstruct(root, request["input_sha"], decisions_from_data(request["decisions"]))
        if reconstructed is None:
            require(artifact["plan"] is None and not artifact["files"], "Candidate differs from clean reconstruction")
        else:
            plan, files = reconstructed
            require(plan == artifact["plan"] and files == validate_artifact(artifact),
                    "Candidate differs from clean reconstruction")
            modes = update_modes(plan)
            for row in artifact["files"]:
                require(row["mode"] == modes.get(row["path"], "100644"), "Candidate mode differs from reconstruction")
    else:
        plan = load_json(blob(root, request["input_sha"], ".release/plan.json"))
        validate_plan(plan)
        require(plan == artifact["plan"], "Merged bundle differs from immutable input")
    return {
        "schema": 1, "request": request, "artifact_digest": artifact["digest"],
        "plan_id": artifact["plan"]["plan_id"] if artifact["plan"] is not None else None,
        "renderer_identity": renderer_identity(),
    }


def validate_verification(artifact, verification):
    fields(verification, ("schema", "request", "artifact_digest", "plan_id", "renderer_identity"))
    require(type(verification["schema"]) is int and verification["schema"] == 1, "Unsupported verification schema")
    require(verification["request"] == artifact["request"]
            and verification["artifact_digest"] == artifact["digest"]
            and verification["plan_id"] == (artifact["plan"]["plan_id"] if artifact["plan"] is not None else None)
            and verification["renderer_identity"] == renderer_identity(),
            "Independent verification identity mismatch")


def verification_provenance(gh, artifact_id, request):
    text(artifact_id, re.compile(r"[1-9]\d*\Z"))
    artifact = gh.get("actions/artifacts/" + artifact_id)
    require(artifact.get("id") == int(artifact_id) and artifact.get("expired") is False
            and artifact.get("name") == f"release-verified-{request['run_id']}-{request['run_attempt']}"
            and artifact.get("workflow_run", {}).get("id") == int(request["run_id"])
            and artifact["workflow_run"].get("head_sha") == request["dispatcher_sha"],
            "Independent verifier artifact provenance mismatch")


def verify_transaction(root):
    plan_path = root / ".release/plan.json"
    plan = None
    if plan_path.exists():
        plan = load_json(plan_path.read_bytes())
        validate_plan(plan)
        require(plan["state"] == "ReadyPlan", "Unanswered release decisions")
    records = previous_transactions(root)
    components, _ = source_inventory(root)
    check_current_versions(root, components, records)
    require(plan is not None or not records, "Prior transaction was removed")
    if plan is not None:
        require(read_decisions((root / ".release/decisions.toml").read_bytes()) == decisions_from_data(plan["decisions"]), "Plan decisions mismatch")
        original_policy = {p: blob(root, plan["input_sha"], p) for p in ("cliff.toml", "tools/release.py")}
        require(policy_digest(original_policy) == plan["policy_digest"], "Plan policy mismatch")
        for item in plan["releases"]:
            require(version_field((root / item["source"]).read_bytes()) == item["target"], "Plan source mismatch")
            heading = f"## [{item['component']} {item['target']}] - {plan['proposal_date']}\n\n{item['notes']}".encode()
            require(heading in (root / "CHANGELOG.md").read_bytes(), "Plan changelog mismatch")
    return records, components


def check_proposal(root, base_sha):
    plan = load_json((root / ".release/plan.json").read_bytes())
    validate_current_plan(plan)
    require(plan["state"] == "ReadyPlan", "Unanswered release decisions")
    text(base_sha, SHA)
    require(base_sha == plan["input_sha"], "Proposal input is no longer current main")
    require(git(root, "show", "-s", "--format=%P", "HEAD").split() == [plan["input_sha"]],
            "Proposal must be one immutable commit on its recorded input")
    originals = tracked_originals(root, plan, plan["input_sha"])
    if plan["schema"] == 2:
        reconstructed = reconstruct(root, plan["input_sha"], decisions_from_data(plan["decisions"]))
        require(reconstructed is not None and reconstructed[0] == plan, "Proposal differs from clean reconstruction")
        expected = reconstructed[1]
    else:
        expected = expected_updates(plan, originals)
    actual = set(git(root, "diff", "--no-renames", "--name-only", plan["input_sha"], "HEAD").splitlines())
    require(actual == set(expected), "Transaction contains unexpected paths")
    modes = update_modes(plan)
    for path, raw in expected.items():
        row = git(root, "ls-tree", "HEAD", "--", path)
        if raw is None:
            require((not row or row.split()[1] == "tree") and (
                not (root / path).exists() or (root / path).is_dir()) and not (root / path).is_symlink(),
                "Deleted proposal path still exists")
            continue
        require(row.startswith(modes.get(path, "100644") + " blob "), f"Invalid proposal file mode for {path}")
        require(blob(root, "HEAD", path) == raw and (root / path).read_bytes() == raw,
                f"Transaction mismatch for {path}")
    verify_transaction(root)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReleaseError("GitHub API redirect refused")


class GitHub:
    def __init__(self, repository, token, opener=None):
        text(repository, re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z"))
        self.repository = repository
        self.token = token
        self.opener = opener or build_opener(NoRedirect())

    def api(self, path, method="GET", body=None, statuses=(200,)):
        require(path.startswith("/") and not path.startswith("//") and "#" not in path, "Invalid API path")
        request = Request(
            "https://api.github.com" + path,
            data=canonical(body) if body is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json",
                "User-Agent": "nilpath-release",
            },
        )
        try:
            response = self.opener.open(request, timeout=60)
            with response:
                status = response.status
                raw = response.read(20_000_001)
        except HTTPError as exc:
            raise ReleaseError(f"GitHub API {method} {path} returned {exc.code}") from exc
        except URLError as exc:
            raise ReleaseError(f"GitHub API transport failed: {exc.reason}") from exc
        require(status in statuses, f"Unexpected GitHub API status {status}")
        require(len(raw) <= 20_000_000, "GitHub response exceeds limit")
        return load_json(raw)

    def path(self, suffix):
        return f"/repos/{self.repository}/{suffix}"

    def get(self, suffix):
        return self.api(self.path(suffix))

    def post(self, suffix, body):
        return self.api(self.path(suffix), "POST", body, (201,))

    def patch(self, suffix, body):
        return self.api(self.path(suffix), "PATCH", body)

    def pages(self, suffix, key=None):
        rows = []
        seen = set()
        for page in range(1, 1001):
            join = "&" if "?" in suffix else "?"
            response = self.get(f"{suffix}{join}per_page=100&page={page}")
            batch = response.get(key) if key and isinstance(response, dict) else response if not key else None
            require(isinstance(batch, list) and len(batch) <= 100, "Malformed paginated response")
            for item in batch:
                require(isinstance(item, dict), "Malformed list item")
                identity = item.get("id", item.get("sha", item.get("ref", item.get("name"))))
                require(identity is not None and identity not in seen, "Repeated pagination item")
                seen.add(identity)
            rows.extend(batch)
            if len(batch) < 100:
                if key:
                    require(type(response.get("total_count")) is int and response["total_count"] == len(rows),
                            "Incomplete paginated result")
                return rows
        raise ReleaseError("GitHub pagination exceeds limit")

    def tree(self, sha):
        text(sha, SHA)
        data = self.get(f"git/trees/{sha}?recursive=1")
        require(data.get("truncated") is False and isinstance(data.get("tree"), list), "Incomplete Git tree")
        result = {}
        for item in data["tree"]:
            path = safe_path(item["path"])
            require(path not in result, "Duplicate tree path")
            text(item["sha"], SHA)
            require(item["mode"] in {"040000", "100644", "100755", "120000", "160000"}, "Unknown tree mode")
            result[path] = item
        return result

    def content(self, tree, path, optional=False, executable=False):
        item = tree.get(path)
        if item is None:
            require(optional, f"Missing required file {path}")
            return None
        allowed = {"100644", "100755"} if executable else {"100644"}
        require(item["mode"] in allowed and item["type"] == "blob", f"Unsafe mode for {path}")
        data = self.get("git/blobs/" + item["sha"])
        require(data.get("encoding") == "base64" and isinstance(data.get("content"), str), "Invalid blob encoding")
        try:
            raw = base64.b64decode(data["content"].replace("\n", ""), validate=True)
        except ValueError as exc:
            raise ReleaseError("Invalid GitHub blob") from exc
        require(data.get("size") == len(raw) and len(raw) <= 2_000_000, "Blob size mismatch")
        require(blob_sha(raw) == item["sha"], "Git blob identity mismatch")
        return raw

    def main_sha(self):
        data = self.get("git/ref/heads/main")
        require(data.get("ref") == "refs/heads/main" and data["object"]["type"] == "commit", "Invalid main ref")
        return text(data["object"]["sha"], SHA)

    def release_create(self, tag, title, body, merged_sha):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.md"
            path.write_text(body)
            env = {**os.environ, "GH_TOKEN": self.token, "GH_HOST": "github.com", "GH_PROMPT_DISABLED": "1"}
            result = subprocess.run(
                ["gh", "release", "create", tag, "--repo", self.repository, "--draft", "--verify-tag",
                 "--target", merged_sha, "--title", title, "--notes-file", str(path)],
                env=env, text=True, capture_output=True,
            )
        require(result.returncode == 0, f"gh release create failed: {result.stderr}")


def owned_proposal(pr, repository):
    require(pr["user"]["login"] == BOT and pr["user"]["id"] == BOT_ID, "Proposal is not bot-owned")
    require(pr["base"]["ref"] == "main" and pr["base"]["repo"]["full_name"] == repository, "Wrong proposal base")
    require((pr["head"]["repo"] or {}).get("full_name") == repository, "Fork proposal refused")
    require(pr["head"]["ref"].startswith("release/proposal-"), "Unexpected proposal branch")
    body = pr.get("body") or ""
    matches = re.findall(r"<!-- nilpath-release-proposal:([0-9a-f]{64}) -->", body)
    require(len(matches) == 1, "Missing or ambiguous proposal ownership marker")
    return matches[0]


def open_proposals(gh):
    proposals = []
    for pr in gh.pages("pulls?state=open&base=main"):
        if proposal_candidate(pr, gh.repository):
            owned_proposal(pr, gh.repository)
            proposals.append(pr)
    return proposals


def proposal_candidate(pr, repository):
    return (pr.get("user", {}).get("login") == BOT and pr["user"].get("id") == BOT_ID
            and (pr.get("head", {}).get("repo") or {}).get("full_name") == repository
            and (pr["head"].get("ref", "").startswith("release/proposal-")
                 or PROPOSAL_MARKER in (pr.get("body") or "")))


def plan_at(gh, sha):
    tree = gh.tree(sha)
    raw = gh.content(tree, ".release/plan.json", optional=True)
    if raw is None:
        return None, tree
    plan = load_json(raw)
    validate_plan(plan)
    return plan, tree


@dataclass(frozen=True)
class ActiveProposal:
    pr: dict
    plan: dict
    decisions: tuple


def active_proposal(gh, pr, expected_head):
    require(pr["state"] == "open", "Resolution requires the open proposal")
    require(pr["head"]["sha"] == expected_head, "Stale resolution head")
    plan, head_tree = plan_at(gh, expected_head)
    require(plan is not None, "Missing proposal plan")
    require(owned_proposal(pr, gh.repository) == plan["plan_id"], "Proposal plan marker mismatch")
    base_tree = gh.tree(plan["input_sha"])
    expected = recorded_updates(gh, plan, base_tree, head_tree)
    expected[".release/decisions.toml"] = gh.content(head_tree, ".release/decisions.toml")
    matching_tree(gh, expected_head, base_tree, expected, update_modes(plan))
    return ActiveProposal(pr, plan, read_decisions(expected[".release/decisions.toml"]))


def selected_decisions(gh, active, input_sha):
    old_input = active.plan["input_sha"]
    if old_input != input_sha:
        comparison = gh.get(f"compare/{old_input}...{input_sha}")
        require(comparison.get("status") == "ahead"
                and comparison.get("merge_base_commit", {}).get("sha") == old_input,
                "Proposal input is not an ancestor of current main")
    accepted = read_decisions(gh.content(gh.tree(input_sha), ".release/decisions.toml"))
    selected = {(d.component, d.commit): d for d in active.decisions}
    for decision in accepted:
        key = (decision.component, decision.commit)
        require(key not in selected or selected[key] == decision, "Conflicting accepted decision")
        selected[key] = decision
    return tuple(sorted(selected.values(), key=lambda d: (d.component, d.commit)))


def superseded_identity(pr):
    matches = re.findall(r"<!-- nilpath-release-supersedes:([1-9]\d*):([0-9a-f]{40}) -->", pr.get("body") or "")
    require(len(matches) <= 1, "Ambiguous supersession identity")
    return (int(matches[0][0]), matches[0][1]) if matches else None


def proposal_context(gh, input_sha, proposal_pr=None, expected_head=None):
    if proposal_pr:
        owned_proposal(gh.get(f"pulls/{proposal_pr}"), gh.repository)
    proposals = open_proposals(gh)
    require(len(proposals) <= 2, "Multiple active release proposals")
    replacement = None
    if len(proposals) == 2:
        pairs = [(old, new) for old in proposals for new in proposals
                 if superseded_identity(new) == (old["number"], old["head"]["sha"])]
        require(len(pairs) == 1, "Conflicting active release proposals or changed original head")
        old, replacement = pairs[0]
        proposals = [old]
        require(proposal_pr in {None, old["number"]}, "Wrong supersession original")
    if proposal_pr:
        require(len(proposals) == 1 and proposals[0]["number"] == proposal_pr,
                "Resolution proposal is no longer active")
    if not proposals:
        require(not proposal_pr and not expected_head, "Resolution proposal is no longer active")
        decisions = read_decisions(gh.content(gh.tree(input_sha), ".release/decisions.toml"))
        return None, None, decisions
    pr = gh.get(f"pulls/{proposals[0]['number']}")
    if replacement:
        replacement = gh.get(f"pulls/{replacement['number']}")
        require(superseded_identity(replacement) == (pr["number"], pr["head"]["sha"]),
                "Original proposal head changed")
    active = active_proposal(gh, pr, expected_head or pr["head"]["sha"])
    if not expected_head:
        require(active.decisions == decisions_from_data(active.plan["decisions"]),
                "Maintainer decisions need explicit resolution")
    return active, replacement, selected_decisions(gh, active, input_sha)


def snapshot(gh, *, mode, proposal_pr, expected_head, merged_sha, event_sha, identity):
    require(mode in {"auto", "prepare", "drafts"}, "Invalid mode")
    input_sha = gh.main_sha()
    kind = "proposal"
    if mode == "auto":
        associated = gh.pages(f"commits/{event_sha}/pulls")
        recognized = [pr for pr in associated if proposal_candidate(pr, gh.repository)]
        require(len(recognized) <= 1, "Ambiguous merged release")
        if recognized:
            proposal_pr = recognized[0]["number"]
            merged_sha = event_sha
            kind = "drafts"
        else:
            require(input_sha == event_sha, "Push input is no longer main")
    if mode == "drafts":
        require(proposal_pr and merged_sha and not expected_head, "Draft retry requires proposal_pr and merged_sha")
        kind = "drafts"
    if kind == "drafts":
        pr = gh.get(f"pulls/{proposal_pr}")
        owned_proposal(pr, gh.repository)
        require(pr["merged"] is True and pr["merge_commit_sha"] == merged_sha, "Wrong merged proposal")
        expected_head = pr["head"]["sha"]
        input_sha = merged_sha
        decisions = ()
    else:
        require(not merged_sha and bool(proposal_pr) == bool(expected_head), "Resolution requires expected_head")
        active, _, decisions = proposal_context(gh, input_sha, proposal_pr, expected_head)
        if active:
            proposal_pr, expected_head = active.pr["number"], active.pr["head"]["sha"]
    request = {
        "schema": 1, "kind": kind, "repository": gh.repository, **identity,
        "input_sha": input_sha, "proposal_pr": proposal_pr, "expected_head": expected_head,
        "merged_sha": merged_sha, "decisions": [asdict(d) for d in decisions],
    }
    validate_request(request)
    return request


def check_provenance(gh, pr, head):
    reviews = gh.pages(f"pulls/{pr['number']}/reviews")
    latest = {}
    for review in reviews:
        if review["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            latest[review["user"]["id"]] = review
    require(not any(r["state"] == "CHANGES_REQUESTED" for r in latest.values()), "Unresolved change request")
    require(any(r["state"] == "APPROVED" and r["commit_id"] == head
                and r["user"]["type"] == "User" and r["author_association"] in {"OWNER", "MEMBER", "COLLABORATOR"}
                for r in latest.values()), "No human approval for exact proposal head")
    workflow = gh.get("actions/workflows/ci.yml")
    require(workflow.get("path") == ".github/workflows/ci.yml" and type(workflow.get("id")) is int, "Invalid CI workflow")
    runs = gh.pages("actions/workflows/ci.yml/runs?" + urlencode({"head_sha": head, "event": "pull_request"}),
                    "workflow_runs")
    associated = gh.pages(f"commits/{head}/pulls")
    require(any(p["number"] == pr["number"] and p["head"]["sha"] == head
                and p["head"]["repo"]["full_name"] == gh.repository
                and p["base"]["repo"]["full_name"] == gh.repository for p in associated),
            "Missing durable PR/head association")
    exact = [run for run in runs if run["head_sha"] == head and run["workflow_id"] == workflow["id"]
             and run["event"] == "pull_request" and run["path"] == ".github/workflows/ci.yml"
             and run["head_repository"]["full_name"] == gh.repository]
    require(exact, "Missing exact-head CI run")
    run = max(exact, key=lambda row: row["id"])
    require(run["status"] == "completed" and run["conclusion"] == "success", "Exact-head CI has not succeeded")
    jobs = gh.pages(f"actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", "jobs")
    for name in ("pr-title", "test-static", "release-plan"):
        matches = [job for job in jobs if job["name"] == name]
        require(len(matches) == 1 and matches[0]["head_sha"] == head
                and matches[0]["status"] == "completed" and matches[0]["conclusion"] == "success",
                f"Missing successful exact-head {name} job")
    checks = gh.pages(f"commits/{head}/check-runs?filter=latest", "check_runs")
    for job in jobs:
        if job["name"] not in {"pr-title", "test-static", "release-plan"}:
            continue
        matches = [check for check in checks if check["name"] == job["name"] and check["head_sha"] == head
                   and check["app"]["id"] == ACTIONS_APP_ID
                   and check["details_url"] == job["html_url"] and check["check_suite"]["id"] == run["check_suite_id"]]
        require(len(matches) == 1 and matches[0]["conclusion"] == "success", "Check provenance mismatch")


@dataclass(frozen=True)
class ReleaseIdentity:
    plan: dict
    merged_sha: str
    head_sha: str
    proposal_pr: int


def release_identity(gh, proposal_pr, merged_sha, supplied_plan):
    pr = gh.get(f"pulls/{proposal_pr}")
    marker = owned_proposal(pr, gh.repository)
    require(pr["state"] == "closed" and pr["merged"] is True and pr["merge_commit_sha"] == merged_sha,
            "Proposal is not merged at the requested SHA")
    text(merged_sha, SHA)
    head = text(pr["head"]["sha"], SHA)
    merged = gh.get("git/commits/" + merged_sha)
    checked = gh.get("git/commits/" + head)
    plan, merged_tree = plan_at(gh, merged_sha)
    require(plan is not None and plan["state"] == "ReadyPlan", "Recognized release has no ready plan")
    require(plan == supplied_plan and marker == plan["plan_id"], "Reviewed plan identity mismatch")
    require([p["sha"] for p in merged["parents"]] == [plan["input_sha"]], "Stale merge or non-squash parent")
    require(merged["tree"]["sha"] == checked["tree"]["sha"], "Merged tree differs from checked proposal")
    require(read_decisions(gh.content(merged_tree, ".release/decisions.toml"))
            == decisions_from_data(plan["decisions"]), "Merged decisions mismatch")
    input_tree = gh.tree(plan["input_sha"])
    require(policy_digest({p: gh.content(input_tree, p) for p in ("cliff.toml", "tools/release.py")})
            == plan["policy_digest"], "Historical policy identity mismatch")
    if not plan["releases"]:
        changed = {p for p in set(input_tree) | set(merged_tree)
                   if input_tree.get(p) != merged_tree.get(p)
                   and (input_tree.get(p, {}).get("type") not in {None, "tree"}
                        or merged_tree.get(p, {}).get("type") not in {None, "tree"})}
        require(changed <= {".release/plan.json", ".release/decisions.toml"},
                "Decision-only transaction has unexpected files")
    for item in plan["releases"]:
        require(version_field(gh.content(merged_tree, item["source"])) == item["target"], "Merged source mismatch")
    return ReleaseIdentity(plan, merged_sha, head, proposal_pr)


def reviewed_release(gh, proposal_pr, merged_sha, supplied_plan):
    reviewed = release_identity(gh, proposal_pr, merged_sha, supplied_plan)
    plan = reviewed.plan
    if plan["releases"] and completed_releases(gh, reviewed):
        return reviewed
    if not plan["releases"] and decision_receipt(gh, reviewed):
        return reviewed
    input_tree = gh.tree(plan["input_sha"])
    expected = recorded_updates(gh, plan, input_tree, gh.tree(merged_sha))
    matching_tree(gh, merged_sha, input_tree, expected, update_modes(plan))
    check_provenance(gh, gh.get(f"pulls/{proposal_pr}"), reviewed.head_sha)
    return reviewed


def completion_marker(gh, reviewed):
    return (f"{COMPLETION_MARKER}1:{gh.repository}:{reviewed.proposal_pr}:{reviewed.head_sha}:"
            f"{reviewed.merged_sha}:{reviewed.plan['plan_id']} -->")


def decision_receipt(gh, reviewed):
    marker = completion_marker(gh, reviewed)
    receipts = [comment for comment in gh.pages(f"issues/{reviewed.proposal_pr}/comments")
                if isinstance(comment.get("user"), dict)
                and comment["user"].get("login") == BOT and comment["user"].get("id") == BOT_ID
                and COMPLETION_MARKER in (comment.get("body") or "")]
    require(len(receipts) <= 1, "Ambiguous decision completion receipt")
    if not receipts:
        return False
    receipt = receipts[0]
    require(receipt.get("body") == marker and type(receipt.get("id")) is int and receipt["id"] > 0,
            "Conflicting or unowned decision completion receipt")
    return True


def release_marker(item, merged_sha, plan_id):
    return f"<!-- nilpath-release:{item['component']}:{item['target']}:{merged_sha}:{plan_id} -->"


def existing_releases(gh):
    result = {}
    for item in gh.pages("releases"):
        tag = text(item.get("tag_name"))
        require(tag not in result, "Ambiguous release tag")
        result[tag] = item
    return result


def existing_tags(gh, wanted):
    tags = {}
    for item in gh.pages("tags"):
        name = text(item.get("name"))
        text(item["commit"]["sha"], SHA)
        if name in wanted:
            ref = gh.get("git/ref/tags/" + quote(name, safe="/"))
            require(ref["ref"] == "refs/tags/" + name, "Tag ref identity mismatch")
            tags[name] = ref["object"]
    return tags


def tag_identity(gh, tag, merged_sha):
    current = gh.get("git/ref/tags/" + quote(tag, safe="/"))
    require(current.get("ref") == "refs/tags/" + tag
            and current["object"]["sha"] == merged_sha and current["object"]["type"] == "commit",
            f"Tag moved or conflicts: {tag}")


def release_receipt(gh, release, item, reviewed, created=False):
    tag = f"{item['component']}/v{item['target']}"
    marker = release_marker(item, reviewed.merged_sha, reviewed.plan["plan_id"])
    markers = re.findall(r"<!-- nilpath-release:[^>]* -->", release.get("body") or "")
    require(release.get("tag_name") == tag and type(release.get("id")) is int and release["id"] > 0
            and markers == [marker], f"Conflicting or unowned release {tag}")
    require(type(release.get("draft")) is bool and type(release.get("prerelease")) is bool,
            "Invalid release state")
    if created:
        require(release["draft"] is True and release["prerelease"] is False
                and release.get("name") == f"{item['component']} {item['target']}",
                "Draft creation identity mismatch")
    tag_identity(gh, tag, reviewed.merged_sha)


def completed_releases(gh, reviewed):
    releases = existing_releases(gh)
    complete = True
    for item in reviewed.plan["releases"]:
        tag = f"{item['component']}/v{item['target']}"
        if tag in releases:
            release_receipt(gh, releases[tag], item, reviewed)
        else:
            complete = False
    return complete


def reconcile_drafts(gh, reviewed, create=True):
    plan, merged_sha = reviewed.plan, reviewed.merged_sha
    if not plan["releases"]:
        if decision_receipt(gh, reviewed):
            return
        require(create, "Incomplete prior decision transaction, retry drafts for its proposal PR")
        gh.post(f"issues/{reviewed.proposal_pr}/comments", {"body": completion_marker(gh, reviewed)})
        require(decision_receipt(gh, reviewed), "Decision completion receipt was not confirmed")
        return
    tags = existing_tags(gh, {f"{item['component']}/v{item['target']}" for item in plan["releases"]})
    releases = existing_releases(gh)
    for item in plan["releases"]:
        tag = f"{item['component']}/v{item['target']}"
        marker = release_marker(item, merged_sha, plan["plan_id"])
        existing_tag = tags.get(tag)
        if existing_tag:
            require(existing_tag["type"] == "commit" and existing_tag["sha"] == merged_sha, f"Conflicting tag {tag}")
        existing = releases.get(tag)
        if existing:
            require(existing_tag is not None, f"Missing release tag {tag}")
            release_receipt(gh, existing, item, reviewed)
            continue
        require(create, f"Incomplete prior release transaction, retry drafts for {tag}")
        if not existing_tag:
            created = gh.post("git/refs", {"ref": "refs/tags/" + tag, "sha": merged_sha})
            require(created["ref"] == "refs/tags/" + tag and created["object"]["sha"] == merged_sha
                    and created["object"]["type"] == "commit", "Created tag identity mismatch")
        tag_identity(gh, tag, merged_sha)
        title = f"{item['component']} {item['target']}"
        gh.release_create(tag, title, item["notes"].rstrip() + "\n\n" + marker + "\n", merged_sha)
        created = existing_releases(gh).get(tag)
        require(created is not None, "Draft creation was not confirmed")
        release_receipt(gh, created, item, reviewed, created=True)


def prior_complete(gh, input_sha):
    plan, _ = plan_at(gh, input_sha)
    commits = gh.pages("commits?" + urlencode({"sha": input_sha, "path": ".release/plan.json"}))
    require(plan is not None or not commits, "Prior transaction was removed")
    require(plan is None or commits, "Missing prior plan provenance")
    for commit in commits:
        merged_sha = commit["sha"]
        historical, _ = plan_at(gh, merged_sha)
        require(historical is not None, "Prior transaction was removed")
        if commit == commits[0]:
            require(historical == plan, "Prior plan provenance mismatch")
        associated = gh.pages(f"commits/{merged_sha}/pulls")
        owned = [p for p in associated if proposal_candidate(p, gh.repository)]
        require(len(owned) == 1, "Prior transaction has no unique proposal")
        reviewed = release_identity(gh, owned[0]["number"], merged_sha, historical)
        reconcile_drafts(gh, reviewed, create=False)


def proposal_body(plan, old=None):
    lines = [
        f"{PROPOSAL_MARKER}{plan['plan_id']} -->",
        f"\nRelease input `{plan['input_sha']}`. State `{plan['state']}`.",
        "\nApprove workflows to run before reviewing the exact proposal head.",
    ]
    if old:
        lines.append(f"<!-- nilpath-release-supersedes:{old['number']}:{old['head']['sha']} -->")
    for item in plan["releases"]:
        lines.append(f"\n- {item['component']} {item['current']} -> {item['target']}")
    for row in plan["requests"]:
        lines.append(f"\n- Decision needed for `{row['component']}` at `{row['commit']}`. Suggested `{row['suggestion']}`. {row['reason']}")
    lines.extend("\n- " + explanation for explanation in plan["explanations"])
    if plan["state"] == "NeedsDecisions":
        lines.append("\nEdit `.release/decisions.toml`, then dispatch `prepare` with this PR number and its exact edited head.")
    lines.append("\nSee `ai_docs/release-workflow.md`. Publication remains manual.")
    return "\n".join(lines)


def recorded_updates(gh, plan, input_tree, final_tree):
    originals = {p: gh.content(input_tree, p, executable=plan["schema"] == 2 and owns(p))
                 for p in input_tree if relevant_path(p, plan) and input_tree[p]["type"] != "tree"}
    payload = {edit["path"]: gh.content(final_tree, edit["path"], executable=True)
               for edit in plan.get("generated", []) if edit["op"] == "put"}
    check_deletion_modes(plan, input_tree)
    return historical_updates(plan, originals, payload)


def matching_tree(gh, sha, original_tree, files, modes=None):
    modes = modes or {}
    expected = {p: (i["mode"], i["sha"]) for p, i in original_tree.items() if i["type"] != "tree"}
    for path, raw in files.items():
        if raw is None:
            expected.pop(path, None)
        else:
            expected[path] = (modes.get(path, "100644"), blob_sha(raw))
    actual = {p: (i["mode"], i["sha"]) for p, i in gh.tree(sha).items() if i["type"] != "tree"}
    require(expected == actual, "Transaction contains unexpected files, modes or bytes")


def supersede(gh, old, replacement):
    number = replacement["number"]
    current = gh.get(f"pulls/{old['number']}")
    require(current["head"]["sha"] == old["head"]["sha"] and current["state"] == "open",
            "Old proposal changed, not superseded")
    gh.post(f"issues/{current['number']}/comments", {"body": f"Superseded by #{number}. No branch was rewritten."})
    current = gh.get(f"pulls/{old['number']}")
    new = gh.get(f"pulls/{number}")
    require(current["head"]["sha"] == old["head"]["sha"] and current["state"] == "open"
            and new["head"]["sha"] == replacement["head"]["sha"] and new["state"] == "open",
            "Proposal changed during supersession")
    closed = gh.patch(f"pulls/{current['number']}", {"state": "closed"})
    require(closed["number"] == old["number"] and closed["state"] == "closed"
            and closed["head"]["sha"] == old["head"]["sha"] and closed["merged"] is False,
            "Supersession was not confirmed")


def create_proposal(gh, artifact, verification):
    files = validate_artifact(artifact)
    validate_verification(artifact, verification)
    request, plan = artifact["request"], artifact["plan"]
    require(request["kind"] == "proposal", "Not a proposal artifact")
    require(gh.main_sha() == request["input_sha"], "Stale preparation input")
    active, replacement, decisions = proposal_context(
        gh, request["input_sha"], request["proposal_pr"], request["expected_head"])
    require([asdict(d) for d in decisions] == request["decisions"], "Resolution changed after planning")
    prior_complete(gh, request["input_sha"])
    if plan is None:
        require(not active, "NoChanges cannot silently discard an active proposal")
        print("No component release changes.")
        return None
    require(plan["input_sha"] == request["input_sha"] and plan["decisions"] == request["decisions"], "Plan/request mismatch")
    original_tree = gh.tree(request["input_sha"])
    originals = {p: gh.content(original_tree, p, executable=plan["schema"] == 2 and owns(p))
                 for p in original_tree if relevant_path(p, plan) and original_tree[p]["type"] != "tree"}
    check_deletion_modes(plan, original_tree)
    require(files == expected_updates(plan, originals, files), "Artifact contains unauthorized file changes")
    modes = update_modes(plan)
    require(all(row["mode"] == modes.get(row["path"], "100644") for row in artifact["files"]),
            "Artifact contains unauthorized file modes")
    if replacement:
        recovered = active_proposal(gh, replacement, replacement["head"]["sha"])
        require(recovered.decisions == decisions_from_data(recovered.plan["decisions"]),
                "Replacement has new maintainer decisions")
        require(selected_decisions(gh, recovered, request["input_sha"]) == decisions,
                "Replacement decisions conflict with original")
        candidate = gh.get("git/commits/" + replacement["head"]["sha"])
        require([p["sha"] for p in candidate["parents"]] == [recovered.plan["input_sha"]],
                "Replacement parent mismatch")
        replacement_tree = gh.tree(recovered.plan["input_sha"])
        matching_tree(gh, replacement["head"]["sha"], replacement_tree,
                      recorded_updates(gh, recovered.plan, replacement_tree, gh.tree(replacement["head"]["sha"])),
                      update_modes(recovered.plan))
        supersede(gh, active.pr, replacement)
        active = recovered
    if active and active.plan == plan:
        matching_tree(gh, active.pr["head"]["sha"], original_tree, files, modes)
        print(f"Matching proposal already exists: {active.pr['number']}")
        return active.pr["number"]
    branch = f"release/proposal-{plan['plan_id']}"
    refs = gh.pages("branches")
    matches = [ref for ref in refs if ref["name"] == branch]
    require(len(matches) <= 1, "Ambiguous proposal branch")
    if matches:
        commit_sha = text(matches[0]["commit"]["sha"], SHA)
        candidate = gh.get("git/commits/" + commit_sha)
        require([p["sha"] for p in candidate["parents"]] == [request["input_sha"]], "Existing branch parent mismatch")
        matching_tree(gh, commit_sha, original_tree, files, modes)
    else:
        entries = []
        for path, raw in sorted(files.items()):
            if raw is None:
                entries.append({"path": path, "mode": modes[path], "type": "blob", "sha": None})
                continue
            new_blob = gh.post("git/blobs", {"content": base64.b64encode(raw).decode(), "encoding": "base64"})
            require(new_blob["sha"] == blob_sha(raw), "Created blob identity mismatch")
            entries.append({"path": path, "mode": modes.get(path, "100644"), "type": "blob", "sha": text(new_blob["sha"], SHA)})
        input_commit = gh.get("git/commits/" + request["input_sha"])
        base_tree = text(input_commit["tree"]["sha"], SHA)
        tree = gh.post("git/trees", {"base_tree": base_tree, "tree": entries})
        require(tree.get("truncated") is False, "Created tree is incomplete")
        commit = gh.post("git/commits", {
            "message": f"chore(release): prepare {plan['plan_id']}", "tree": text(tree["sha"], SHA),
            "parents": [request["input_sha"]],
        })
        commit_sha = text(commit["sha"], SHA)
        matching_tree(gh, commit_sha, original_tree, files, modes)
        require(gh.main_sha() == request["input_sha"], "Main moved before proposal creation")
        created_ref = gh.post("git/refs", {"ref": "refs/heads/" + branch, "sha": commit_sha})
        require(created_ref["ref"] == "refs/heads/" + branch and created_ref["object"]["sha"] == commit_sha
                and created_ref["object"]["type"] == "commit", "Created proposal ref identity mismatch")
    created = gh.post("pulls", {
        "title": "chore(release): " + ("decisions needed" if plan["requests"] else "prepare component releases"),
        "head": branch, "base": "main", "draft": True, "body": proposal_body(plan, active.pr if active else None),
    })
    require(created.get("draft") is True and created["head"]["sha"] == commit_sha
            and created["head"]["ref"] == branch, "Draft PR creation mismatch")
    require(owned_proposal(created, gh.repository) == plan["plan_id"], "Created proposal plan mismatch")
    require(type(created.get("number")) is int, "Missing created PR number")
    if active:
        supersede(gh, active.pr, created)
    return created["number"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "prepare", "bundle", "check", "check-proposal", "check-pr", "verify-bundle"):
        help_text = "Validate release history or an exact bot-owned proposal." if name == "check-pr" else None
        command = commands.add_parser(name, description=help_text)
        command.add_argument("--root", type=Path, default=Path.cwd())
        if name in {"plan", "prepare", "bundle"}:
            command.add_argument("--request", type=Path, required=name != "plan")
        if name == "bundle":
            command.add_argument("--output", type=Path, required=True)
        if name in {"check-proposal", "check-pr"}:
            command.add_argument("--base-sha", required=True)
        if name == "verify-bundle":
            command.add_argument("--request", type=Path, required=True)
            command.add_argument("--artifact", type=Path, required=True)
            command.add_argument("--output", type=Path, required=True)
    commands.add_parser("snapshot").add_argument("--output", type=Path, required=True)
    writer = commands.add_parser("write")
    writer.add_argument("--artifact", type=Path, required=True)
    writer.add_argument("--verification-artifact-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in {"snapshot", "write"}:
            gh = GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
            request = snapshot(
                gh, mode=os.environ.get("RELEASE_MODE") or "auto",
                proposal_pr=int(os.environ["PROPOSAL_PR"]) if os.environ.get("PROPOSAL_PR") else None,
                expected_head=os.environ.get("EXPECTED_HEAD") or None,
                merged_sha=os.environ.get("MERGED_SHA") or None,
                event_sha=os.environ["GITHUB_SHA"], identity={
                    "run_id": os.environ["GITHUB_RUN_ID"],
                    "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
                    "dispatcher_sha": os.environ["DISPATCHER_SHA"],
                },
            )
            if args.command == "snapshot":
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(canonical(request) + b"\n")
                if os.environ.get("GITHUB_OUTPUT"):
                    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
                        output.write(f"kind={request['kind']}\ninput_sha={request['input_sha']}\n")
                return 0
            require(args.artifact.is_file() and not args.artifact.is_symlink()
                    and not args.artifact.parent.is_symlink(), "Invalid artifact file")
            require(list(args.artifact.parent.iterdir()) == [args.artifact], "Artifact must contain exactly one bundle")
            raw = args.artifact.read_bytes()
            require(len(raw) <= 10_000_000, "Artifact exceeds limit")
            verified = load_json(raw)
            fields(verified, ("artifact", "verification"))
            artifact = verified["artifact"]
            require(artifact["request"] == request, "Artifact snapshot is stale or mismatched")
            verification_provenance(gh, args.verification_artifact_id, request)
            if request["kind"] == "proposal":
                number = create_proposal(gh, artifact, verified["verification"])
                print(f"Proposal result {number}.")
            else:
                validate_artifact(artifact)
                validate_verification(artifact, verified["verification"])
                reviewed = reviewed_release(gh, request["proposal_pr"], request["merged_sha"], artifact["plan"])
                reconcile_drafts(gh, reviewed)
                print("Reviewed draft reconciliation complete.")
            return 0
        root = args.root.resolve()
        if args.command == "verify-bundle":
            request = load_json(args.request.read_bytes())
            artifact = load_json(args.artifact.read_bytes())
            verification = verify_bundle(root, request, artifact)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(canonical({"artifact": artifact, "verification": verification}) + b"\n")
            print("Independent clean reconstruction passed.")
            return 0
        if args.command == "check-pr":
            event = load_json(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())
            pr = event["pull_request"]
            require(pr["head"]["sha"] == git(root, "rev-parse", "HEAD"), "PR head mismatch")
            if proposal_candidate(pr, event["repository"]["full_name"]):
                plan = load_json((root / ".release/plan.json").read_bytes())
                require(owned_proposal(pr, event["repository"]["full_name"]) == plan["plan_id"], "Proposal marker mismatch")
                check_proposal(root, args.base_sha)
            else:
                verify_transaction(root)
            print("PR release checks passed.")
            return 0
        if args.command == "check-proposal":
            check_proposal(root, args.base_sha)
            print("Exact proposal checks passed.")
            return 0
        if args.command == "check":
            verify_transaction(root)
            print("Release provenance checks passed.")
            return 0
        request = load_json(args.request.read_bytes()) if args.request else None
        if args.command == "bundle":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(canonical(bundle(root, request)) + b"\n")
            return 0
        if args.request is not None:
            validate_request(request)
        decisions = decisions_from_data(request["decisions"]) if request else read_decisions((root / ".release/decisions.toml").read_bytes())
        result = propose(root, decisions)
        if isinstance(result, NoChanges):
            print(json.dumps({"state": "NoChanges", "explanations": result.explanations}))
        else:
            if args.command == "prepare":
                require(request["input_sha"] == result.plan["input_sha"], "Request input mismatch")
                prepare(root, result.plan)
            print(json.dumps(result.plan, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"release: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

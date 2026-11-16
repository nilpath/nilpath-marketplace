"""Render one release from trusted base code, reading its candidate only as Git data."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import tomllib

from open_release import (
    ROOT, SHA, ReleaseBump, ReleaseError, blob, gh_api, git, replace_version,
    repository, require, run, version_field,
)

REGISTRIES = (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json",
              ".github/plugin/marketplace.json")
CLIENTS = ("claude", "copilot", "codex")


@contextmanager
def worktree(root, sha):
    with tempfile.TemporaryDirectory(prefix="nilpath-prepare-") as directory:
        work = Path(directory) / "work"
        git(root, "-c", "core.hooksPath=/dev/null", "worktree", "add", "--detach", str(work), sha)
        try:
            yield work
        finally:
            git(root, "worktree", "remove", "--force", str(work))


def release_request(root, base_sha, head_sha):
    require(SHA.fullmatch(base_sha) and SHA.fullmatch(head_sha), "Expected full commit SHAs")
    require(git(root, "merge-base", base_sha, head_sha) == base_sha,
            "Release is stale. Start from the latest main; do not rebase prepared output.")
    paths = git(root, "diff", "--name-only", "--no-renames", base_sha, head_sha).splitlines()
    sources = [p for p in paths if re.fullmatch(r"src/plugins/[a-z0-9-]+/plugin.yaml", p)]
    require(len(sources) == 1, "A release must bump exactly one plugin")
    source = sources[0]
    before, after = blob(root, base_sha, source), blob(root, head_sha, source)
    release = ReleaseBump(source.split("/")[2], version_field(before), version_field(after))
    require(after == replace_version(before, release.target_version), "Only the version scalar may change in plugin.yaml")
    allowed = {source, "README.md", "CHANGELOG.md", f"src/plugins/{release.plugin}/README.md", *REGISTRIES}
    require(all(p in allowed or any(p.startswith(f"dist/{client}/plugins/{release.plugin}/") for client in CLIENTS)
                for p in paths), "Release contains unrelated edits or executable candidate code")
    return release


def update_readmes(work, release):
    for path, pattern in (
        ("README.md", rb"(?m)^(\| \*\*" + release.plugin.encode() + rb"\*\* \| )([^\r\n|]+)( \|)"),
        (f"src/plugins/{release.plugin}/README.md", rb"(?m)^(Version: \*\*)([^*\r\n]+)(\*\*)"),
    ):
        target = work / path
        if not target.exists():
            require(path != "README.md", "Missing root README.md")
            continue
        raw = target.read_bytes()
        matches = list(re.finditer(pattern, raw))
        require(len(matches) == 1 if path == "README.md" else len(matches) <= 1,
                f"Missing or ambiguous current version in {path}")
        if matches:
            require(matches[0][2] == release.previous_version.encode(), f"Stale current version in {path}")
            target.write_bytes(re.sub(pattern, lambda m: m[1] + release.target_version.encode() + m[3], raw))


def release_anchor(root, base_sha, release):
    expected = f"{release.plugin}/v{release.previous_version}"
    tags = git(root, "tag", "--list", f"{release.plugin}/v*").splitlines()
    require(release.tag not in tags, f"Tag {release.tag} already exists; it cannot identify a new release")
    if expected in tags:
        anchor = git(root, "rev-parse", f"refs/tags/{expected}^{{commit}}")
    else:
        require(not tags, f"Missing previous tag {expected}; plugin tag history is inconsistent")
        data = tomllib.loads(blob(root, base_sha, ".release/baselines.toml").decode())
        anchor = data.get("baseline", {}).get(release.plugin, "")
        require(isinstance(anchor, str) and SHA.fullmatch(anchor), "Missing reviewed plugin baseline")
    require(git(root, "merge-base", anchor, base_sha) == anchor, "Release anchor is not an ancestor of the base")
    require(version_field(blob(root, anchor, release.source)) == release.previous_version,
            "Release anchor version does not match the previous source version")
    return anchor


def release_notes(root, base_sha, release):
    anchor = release_anchor(root, base_sha, release)
    require(run(root, "git-cliff", "--version").decode().strip() == "git-cliff 2.13.1",
            "Expected pinned git-cliff 2.13.1")
    args = ["git-cliff", f"{anchor}..{base_sha}", "--offline", "--no-exec",
            "--config", str(root / "cliff.toml"), "--ignore-tags", ".*", "--strip", "all"]
    for path in (f"src/plugins/{release.plugin}/**", "src/harnesses/**", "tools/buildkit/**",
                 "src/marketplace.yaml"):
        args += ["--include-path", path]
    notes = run(root, *args).decode().strip()
    return notes + "\n" if notes else "No shipped changes since the previous release.\n"


def registry_overlay(installed, generated):
    if isinstance(installed, dict) and isinstance(generated, dict):
        return {**installed, **{key: registry_overlay(installed.get(key), value)
                               for key, value in generated.items()}}
    return generated


def replace_registry_entry(raw, rendered, plugin):
    """Splice only the chosen JSON entry; leave every other entry and metadata byte alone."""
    decoder = json.JSONDecoder()
    text = raw.decode()
    original = json.loads(text)
    new = json.loads(rendered)
    entries = original["plugins"]
    require(len({e["name"] for e in entries}) == len(entries), "Duplicate installed registry plugin")
    selected = [e for e in new["plugins"] if e["name"] == plugin]
    require(len(selected) <= 1, "Duplicate generated registry plugin")
    position = text.index("{") + 1
    while True:
        position = re.compile(r"\s*").match(text, position).end()
        key, end = decoder.raw_decode(text, position)
        position = re.compile(r"\s*:\s*").match(text, end).end()
        if key == "plugins":
            start = position
            break
        _, position = decoder.raw_decode(text, position)
        position = re.compile(r"\s*,\s*").match(text, position).end()
    require(text[start] == "[", "Registry plugins must be an array")
    spans = []
    position = start + 1
    for entry in entries:
        position = re.compile(r"[\s,]*").match(text, position).end()
        _, end = decoder.raw_decode(text, position)
        spans.append((position, end))
        position = end
    chosen = next((i for i, e in enumerate(entries) if e["name"] == plugin), None)
    replacement = None
    if selected:
        replacement = registry_overlay(entries[chosen] if chosen is not None else {}, selected[0])
        replacement = json.dumps(replacement, indent=2, ensure_ascii=False).replace("\n", "\n    ")
    if chosen is not None:
        left, right = spans[chosen]
        if replacement is None:
            if chosen + 1 < len(spans):
                right = spans[chosen + 1][0]
            elif chosen:
                left = spans[chosen - 1][1]
            replacement = ""
        return (text[:left] + replacement + text[right:]).encode()
    if replacement is None:
        return raw
    position = spans[-1][1] if spans else start + 1
    return (text[:position] + (",\n    " if spans else "\n    ") + replacement + text[position:]).encode()


def changelog_offset(raw):
    match = re.search(rb"(?m)^## ", raw)
    require(match is not None, "CHANGELOG.md must contain an existing second-level section")
    return match.start()


def render_release(work, base_sha, release):
    sys.path.insert(0, str(ROOT / "tools/buildkit/src"))
    from buildkit.build import build

    source = work / release.source
    source.write_bytes(replace_version(source.read_bytes(), release.target_version))
    update_readmes(work, release)
    changelog = work / "CHANGELOG.md"
    old = changelog.read_bytes()
    offset = changelog_offset(old)
    section = f"## {release.tag}\n\n".encode() + release_notes(work, base_sha, release).encode() + b"\n"
    changelog.write_bytes(old[:offset] + section + old[offset:])
    with tempfile.TemporaryDirectory(prefix="nilpath-render-") as directory:
        output = Path(directory)
        build(work, out_root=output)
        for client in CLIENTS:
            relative = f"dist/{client}/plugins/{release.plugin}"
            target = work / relative
            if target.exists():
                shutil.rmtree(target)
            if (output / relative).exists():
                shutil.copytree(output / relative, target)
        for registry in REGISTRIES:
            target = work / registry
            target.write_bytes(replace_registry_entry(target.read_bytes(), (output / registry).read_bytes(), release.plugin))


def check_live_pr(root, repo, number, base_sha, head_sha, release):
    pr = gh_api(root, repo, f"pulls/{number}")
    require(pr["state"] == "open" and not pr["merged"], "Release PR is not open")
    require(pr["base"]["repo"]["full_name"] == repo and pr["head"]["repo"]["full_name"] == repo,
            "Release PR must be in the same repository")
    require(pr["base"]["ref"] == "main" and pr["head"]["ref"] == release.branch, "Invalid release branch")
    require(pr["base"]["sha"] == base_sha and pr["head"]["sha"] == head_sha,
            "PR base or head changed. Re-run the workflow on the current request.")
    require(gh_api(root, repo, "git/ref/heads/main")["object"]["sha"] == base_sha,
            "main advanced. Close this stale request and open a fresh release from main.")
    return pr


def prepare_release(base_sha, head_sha, check_only=False, *, root=ROOT, pr_number=None, head_ref=None):
    require(check_only or pr_number is not None, "Preparation requires a PR number, or use check_only=True")
    release = release_request(root, base_sha, head_sha)
    require(head_ref is None or head_ref == release.branch, "Invalid release branch")
    repo = repository(root) if pr_number is not None else None
    live_head = head_sha
    if repo:
        live_head = gh_api(root, repo, f"pulls/{pr_number}")["head"]["sha"]
        check_live_pr(root, repo, pr_number, base_sha, live_head, release)
        if live_head != head_sha:
            git(root, "fetch", "--no-tags", "origin", live_head)
            require(git(root, "show", "-s", "--format=%P", live_head) == head_sha,
                    "PR head changed outside exact preparation. Re-run on the current request.")
    with worktree(root, base_sha) as work:
        (work / release.source).write_bytes(replace_version(blob(root, base_sha, release.source), release.target_version))
        git(work, "add", "--", release.source)
        request_tree = git(work, "write-tree")
        render_release(work, base_sha, release)
        git(work, "add", "--all")
        expected = git(work, "write-tree")
        candidate = git(root, "rev-parse", f"{head_sha}^{{tree}}")
        require(candidate in {request_tree, expected}, "Candidate is neither a scalar-only request nor the exact prepared release")
        if live_head != head_sha:
            require(git(root, "rev-parse", f"{live_head}^{{tree}}") == expected,
                    "PR head changed outside exact preparation. Re-run on the current request.")
        if check_only:
            require(candidate == expected, "Release is not prepared yet. Wait for preparation or re-run its failed job.")
        elif repo:
            check_live_pr(root, repo, pr_number, base_sha, live_head, release)
            if candidate != expected and live_head == head_sha:
                commit = run(work, "git", "-c", "user.name=github-actions[bot]", "-c",
                             "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                             "commit-tree", expected, "-p", head_sha,
                             input=f"chore({release.plugin}): prepare {release.tag}\n".encode()).decode().strip()
                try:
                    git(root, "push", "origin", f"--force-with-lease=refs/heads/{release.branch}:{head_sha}",
                        f"{commit}:refs/heads/{release.branch}")
                except ReleaseError as exc:
                    raise ReleaseError(f"{exc}\nNo branch was overwritten. Inspect the PR head, then Re-run jobs. "
                                       "If main advanced, open a fresh request instead.") from exc
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--head-ref")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--pr", type=int)
    args = parser.parse_args()
    try:
        release = prepare_release(args.base_sha, args.head_sha, args.check, pr_number=args.pr, head_ref=args.head_ref)
        print(f"Validated {release.tag}" if args.check else f"Prepared {release.tag}. Approve workflows to run if GitHub requires it.")
    except (ReleaseError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()

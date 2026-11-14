import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import release as r


IDENTITY = {"run_id": "42", "run_attempt": "1", "dispatcher_sha": "d" * 40}


def command(root, *args):
    return subprocess.check_output(args, cwd=root, text=True).strip()


def commit(root, message):
    command(root, "git", "add", ".")
    command(root, "git", "-c", "user.name=Tester", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-qm", message)
    return command(root, "git", "rev-parse", "HEAD")


def write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


@pytest.fixture
def repo(tmp_path):
    command(tmp_path, "git", "init", "-q", "-b", "main")
    shutil.copytree(ROOT / "src/harnesses", tmp_path / "src/harnesses")
    shutil.copy(ROOT / "src/marketplace.yaml", tmp_path / "src/marketplace.yaml")
    shutil.copy(ROOT / "cliff.toml", tmp_path / "cliff.toml")
    (tmp_path / "tools").mkdir()
    shutil.copy(ROOT / "tools/release.py", tmp_path / "tools/release.py")
    shutil.copy(ROOT / "tools/pr_conventions.sh", tmp_path / "tools/pr_conventions.sh")
    shutil.copytree(ROOT / ".github/workflows", tmp_path / ".github/workflows")
    for name, version in (("alpha", "1.2.3"), ("beta", "0.4.8")):
        write(tmp_path, f"src/plugins/{name}/plugin.yaml", f"name: {name}\nversion: {version}\n")
        write(tmp_path, f"src/plugins/{name}/README.md", f"# {name}\n\nVersion: **{version}**\n\nHistorical 0.0.6 and pstack 0.15.30.\n")
        write(tmp_path, f"src/plugins/{name}/skills/one/SKILL.md.j2", "original\n")
    write(tmp_path, "README.md", "| **alpha** | 1.2.3 | a |\n| **beta** | 0.4.8 | b |\nHistorical nstack 0.0.6.\n")
    (tmp_path / "CHANGELOG.md").write_bytes(r.PREFIX + b"# Old\n\n## [Unreleased]\nunchanged\n")
    write(tmp_path, ".release/decisions.toml", "# Empty\n")
    initial = commit(tmp_path, "feat: initialize")
    write(tmp_path, ".release/baselines.toml", f'[baseline]\nalpha = "{initial}"\nbeta = "{initial}"\nnilpath-marketplace = "{initial}"\n')
    commit(tmp_path, "ci: adopt release automation")
    return tmp_path


def change(root, message, name="alpha", path="skills/one/SKILL.md.j2"):
    write(root, f"src/plugins/{name}/{path}", message + "\n")
    return commit(root, message)


def request(input_sha, **changes):
    return {
        "schema": 1, "kind": "proposal", "repository": "nilpath/test", **IDENTITY,
        "input_sha": input_sha, "proposal_pr": None, "expected_head": None,
        "merged_sha": None, "decisions": [], **changes,
    }


def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


class FakeGitHub(r.GitHub):
    def __init__(self, root):
        super().__init__("nilpath/test", "fake")
        self.root = root
        self.main = command(root, "git", "rev-parse", "HEAD")
        self.blobs = {}
        self.trees = {}
        self.commits = {}
        self.refs = {}
        self.prs = {}
        self.tags = {}
        self.releases = []
        self.comments = {}
        self.writes = []
        self.fail = None
        self.routes = {}
        self.load_commit(self.main)

    def load_commit(self, sha):
        rows = command(self.root, "git", "ls-tree", "-r", sha).splitlines()
        tree = {}
        for line in rows:
            meta, path = line.split("\t")
            mode, kind, object_sha = meta.split()
            tree[path] = {"mode": mode, "type": kind, "sha": object_sha, "path": path}
            if kind == "blob":
                self.blobs[object_sha] = r.blob(self.root, sha, path)
        tree_sha = command(self.root, "git", "rev-parse", sha + "^{tree}")
        self.trees[sha] = tree
        self.trees[tree_sha] = tree
        parents = command(self.root, "git", "show", "-s", "--format=%P", sha).split()
        self.commits[sha] = {"sha": sha, "tree": {"sha": tree_sha}, "parents": [{"sha": p} for p in parents]}

    def get(self, suffix):
        if suffix in self.routes:
            response = self.routes[suffix]
            if isinstance(response, Exception):
                raise response
            return copy.deepcopy(response)
        if suffix == "git/ref/heads/main":
            return {"ref": "refs/heads/main", "object": {"type": "commit", "sha": self.main}}
        if suffix.startswith("git/commits/"):
            return copy.deepcopy(self.commits[suffix.removeprefix("git/commits/")])
        if suffix.startswith("git/ref/tags/"):
            tag = suffix.removeprefix("git/ref/tags/")
            return {"ref": "refs/tags/" + tag, "object": self.tags[tag]}
        if suffix.startswith("pulls/") and suffix.count("/") == 1:
            return copy.deepcopy(self.prs[int(suffix.split("/")[1])])
        if suffix.startswith("git/trees/"):
            sha = suffix.removeprefix("git/trees/").split("?")[0]
            return {"truncated": False, "tree": copy.deepcopy(list(self.trees[sha].values()))}
        if suffix.startswith("git/blobs/"):
            raw = self.blobs[suffix.removeprefix("git/blobs/")]
            return {"encoding": "base64", "size": len(raw), "content": base64.b64encode(raw).decode()}
        if "per_page=" in suffix:
            page = int(suffix.rsplit("page=", 1)[1])
            if suffix.startswith("pulls?"):
                return [copy.deepcopy(p) for p in self.prs.values() if p["state"] == "open"] if page == 1 else []
            if suffix.startswith("tags?"):
                return [{"name": tag, "commit": {"sha": obj["sha"]}} for tag, obj in self.tags.items()] if page == 1 else []
            if suffix.startswith("branches?"):
                return [{"name": ref.removeprefix("refs/heads/"), "commit": {"sha": sha}} for ref, sha in self.refs.items()] if page == 1 else []
            if suffix.startswith("releases?"):
                return copy.deepcopy(self.releases) if page == 1 else []
            if suffix.startswith("issues/") and "/comments?" in suffix:
                number = int(suffix.split("/")[1])
                return copy.deepcopy(self.comments.get(number, [])) if page == 1 else []
            if suffix.startswith("commits?"):
                return []
        if suffix.startswith("compare/"):
            old, new = suffix.removeprefix("compare/").split("...")
            ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", old, new], cwd=self.root).returncode == 0
            return {"status": "ahead" if ancestor else "diverged", "merge_base_commit": {"sha": old if ancestor else new}}
        raise AssertionError(f"Unmocked GET {suffix}")

    def mutate(self, suffix, body):
        self.writes.append((suffix, copy.deepcopy(body)))
        if self.fail == suffix:
            self.fail = None
            raise r.ReleaseError("Injected remote failure")

    def post(self, suffix, body):
        self.mutate(suffix, body)
        if suffix == "git/blobs":
            raw = base64.b64decode(body["content"])
            sha = blob_sha(raw)
            self.blobs[sha] = raw
            return {"sha": sha}
        if suffix == "git/trees":
            assert body["base_tree"] not in self.commits, "base_tree requires a tree object, not a commit"
            tree = copy.deepcopy(self.trees[body["base_tree"]])
            for entry in body["tree"]:
                tree[entry["path"]] = entry
            sha = hashlib.sha1(r.canonical(tree)).hexdigest()
            self.trees[sha] = tree
            return {"sha": sha, "truncated": False}
        if suffix == "git/commits":
            sha = hashlib.sha1(r.canonical(body)).hexdigest()
            self.commits[sha] = {"sha": sha, "tree": {"sha": body["tree"]},
                                 "parents": [{"sha": p} for p in body["parents"]]}
            self.trees[sha] = self.trees[body["tree"]]
            return {"sha": sha}
        if suffix == "git/refs":
            if body["ref"].startswith("refs/tags/"):
                tag = body["ref"].removeprefix("refs/tags/")
                self.tags[tag] = {"type": "commit", "sha": body["sha"]}
            else:
                self.refs[body["ref"]] = body["sha"]
            return {"ref": body["ref"], "object": {"type": "commit", "sha": body["sha"]}}
        if suffix == "pulls":
            number = len(self.prs) + 1
            pr = {
                "number": number, "id": number, "user": {"login": r.BOT, "id": r.BOT_ID},
                "head": {"ref": body["head"], "sha": self.refs["refs/heads/" + body["head"]],
                         "repo": {"full_name": self.repository}},
                "base": {"ref": "main", "repo": {"full_name": self.repository}},
                "body": body["body"], "state": "open", "draft": body["draft"], "merged": False,
            }
            self.prs[number] = pr
            return copy.deepcopy(pr)
        if suffix.endswith("/comments"):
            number = int(suffix.split("/")[1])
            comments = self.comments.setdefault(number, [])
            comment = {"id": 200 + len(comments), "body": body["body"], "user": {"login": r.BOT, "id": r.BOT_ID}}
            comments.append(comment)
            return copy.deepcopy(comment)
        raise AssertionError(f"Unmocked POST {suffix}")

    def patch(self, suffix, body):
        self.mutate(suffix, body)
        number = int(suffix.split("/")[1])
        self.prs[number].update(body)
        return copy.deepcopy(self.prs[number])

    def release_create(self, tag, title, body, merged_sha):
        self.mutate("release-create", {"tag": tag, "title": title, "body": body, "target": merged_sha})
        self.releases.append({"id": len(self.releases) + 1, "tag_name": tag, "name": title, "body": body,
                              "draft": True, "prerelease": False, "target_commitish": merged_sha})


@pytest.fixture
def prepared(repo):
    change(repo, "fix(alpha): repair instruction")
    gh = FakeGitHub(repo)
    plan = r.propose(repo).plan
    r.prepare(repo, plan)
    artifact = r.bundle(repo, request(plan["input_sha"]))
    return repo, gh, artifact


def test_tagless_adoption_and_actual_cli(repo):
    result = r.propose(repo)
    assert isinstance(result, r.NoChanges)
    assert result.explanations[-1] == "Repository-only changes do not bump shipped components."
    result = subprocess.run([sys.executable, str(ROOT / "tools/release.py"), "plan", "--root", str(repo)],
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"] == "NoChanges"
    assert not (repo / ".release/plan.json").exists()


def test_independent_bumps_and_real_cliff_retains_unknown(repo):
    a = change(repo, "fix(alpha): repair instruction")
    b = change(repo, "feat(beta): add workflow", "beta")
    plan = r.propose(repo).plan
    assert [(i["component"], i["current"], i["target"]) for i in plan["releases"]] == [
        ("alpha", "1.2.3", "1.2.4"), ("beta", "0.4.8", "0.5.0")]
    assert "Repair instruction" in plan["releases"][0]["notes"]
    assert a in plan["releases"][0]["notes"]
    unknown = change(repo, "An unusual instruction")
    blocked = r.propose(repo)
    assert isinstance(blocked, r.NeedsDecisions)
    assert blocked.plan["releases"] == []
    assert blocked.plan["requests"] == [{
        "component": "alpha", "commit": unknown, "suggestion": "patch",
        "reason": "Unknown or nonconventional commit requires review."}]
    resolved = r.propose(repo, (r.Decision("alpha", unknown, "patch", "Reviewed wording only."),))
    assert "An unusual instruction" in resolved.plan["releases"][0]["notes"]
    assert resolved.plan["releases"][1]["commits"] == [b]


@pytest.mark.parametrize("version,message,bump,target,blocked", [
    ("0.0.7", "feat(alpha): addition", "minor", "0.0.8", True),
    ("0.2.1", "feat(alpha): addition", "minor", "0.3.0", False),
    ("0.2.1", "fix(alpha)!: removal", "major", "0.2.2", True),
    ("1.2.3", "fix(alpha)!: removal", "major", "2.0.0", False),
])
def test_pre_one_policy(repo, version, message, bump, target, blocked):
    source = repo / "src/plugins/alpha/plugin.yaml"
    source.write_text(f"name: alpha\nversion: {version}\n")
    anchor = commit(repo, "chore: establish reviewed fixture baseline")
    baselines = repo / ".release/baselines.toml"
    baselines.write_text(baselines.read_text().replace(r.source_inventory(repo)[0][0].baseline, anchor))
    commit(repo, "ci: accept baseline")
    sha = change(repo, message)
    result = r.propose(repo)
    if blocked:
        assert isinstance(result, r.NeedsDecisions)
        assert result.plan["requests"][0]["suggestion"] == bump
        result = r.propose(repo, (r.Decision("alpha", sha, "patch", "Reviewed pre-one compatibility."),))
    assert result.plan["releases"][0]["target"] == target


@pytest.mark.parametrize("message,path,remove", [
    ("fix(beta): contradictory", "skills/one/SKILL.md.j2", False),
    ("fix(alpha): removed", "skills/one/SKILL.md.j2", True),
    ("chore(alpha): unknown", "skills/one/SKILL.md.j2", False),
])
def test_ambiguous_evidence_is_never_patch_fallback(repo, message, path, remove):
    if remove:
        (repo / f"src/plugins/alpha/{path}").unlink()
        sha = commit(repo, message)
    else:
        sha = change(repo, message, path=path)
    result = r.propose(repo)
    assert isinstance(result, r.NeedsDecisions)
    assert result.plan["requests"][0]["commit"] == sha
    assert result.plan["releases"] == []


def test_added_skill_is_minor_even_with_fix(repo):
    change(repo, "fix(alpha): additional skill", path="skills/two/SKILL.md.j2")
    assert r.propose(repo).plan["releases"][0]["target"] == "1.3.0"


def test_added_support_document_is_not_a_new_skill(repo):
    change(repo, "docs(alpha): add reference", path="skills/one/references/example.md")
    assert r.propose(repo).plan["releases"][0]["target"] == "1.2.4"


def test_qualified_tags_do_not_replace_component_baselines(repo):
    command(repo, "git", "tag", "alpha/v1.2.3")
    command(repo, "git", "tag", "beta/v0.4.8")
    sha = change(repo, "fix(beta): repair guidance", "beta")
    plan = r.propose(repo).plan
    assert [(item["component"], item["target"], item["commits"]) for item in plan["releases"]] == [
        ("beta", "0.4.9", [sha])]


def test_marketplace_is_separate_and_requires_explicit_decision(repo):
    source = repo / "src/marketplace.yaml"
    source.write_text(source.read_text().replace("A marketplace for my claude code extensions", "Updated marketplace metadata"))
    sha = commit(repo, "fix(nilpath-marketplace): metadata")
    result = r.propose(repo)
    assert result.plan["releases"] == []
    assert result.plan["requests"] == [{
        "component": "nilpath-marketplace", "commit": sha, "suggestion": "patch",
        "reason": "Marketplace release-bearing metadata requires its own severity decision."}]
    ready = r.propose(repo, (r.Decision("nilpath-marketplace", sha, "patch", "Marketplace description update."),))
    assert [(i["component"], i["target"]) for i in ready.plan["releases"]] == [("nilpath-marketplace", "0.1.1")]


def test_shared_change_requires_shipped_difference_and_decision(repo):
    write(repo, "tools/buildkit/change.txt", "builder change")
    unchanged = commit(repo, "fix: builder")
    result = r.propose(repo)
    assert isinstance(result, r.NoChanges)
    assert f"alpha: {unchanged} shared change leaves shipped trees unchanged." in result.explanations
    write(repo, "tools/buildkit/change.txt", "builder change two")
    write(repo, "dist/claude/plugins/alpha/skills/one/SKILL.md", "changed")
    sha = commit(repo, "fix: shared builder output")
    result = r.propose(repo)
    assert result.plan["requests"] == [{
        "component": "alpha", "commit": sha, "suggestion": "patch",
        "reason": "Shared code changes shipped output. Decide severity for this component."}]


def test_new_plugin_confirms_authored_version(repo):
    write(repo, "src/plugins/gamma/plugin.yaml", "name: gamma\nversion: 0.7.2\n")
    write(repo, "src/plugins/gamma/README.md", "# Gamma\n")
    write(repo, "README.md", (repo / "README.md").read_text() + "| **gamma** | 0.7.2 | new |\n")
    sha = commit(repo, "feat(gamma): new plugin")
    blocked = r.propose(repo)
    assert blocked.plan["requests"][0]["suggestion"] == "initial"
    ready = r.propose(repo, (r.Decision("gamma", sha, "initial", "Authored version accepted."),))
    item = ready.plan["releases"][0]
    assert (item["component"], item["current"], item["target"], item["baseline"]) == ("gamma", "0.7.2", "0.7.2", None)


def test_exact_updates_keep_historical_strings_and_legacy_bytes(repo):
    change(repo, "fix(alpha): repaired")
    plan = r.propose(repo).plan
    legacy = (repo / "CHANGELOG.md").read_bytes().split(r.BOUNDARY)[1]
    r.prepare(repo, plan)
    assert (repo / "src/plugins/alpha/plugin.yaml").read_text() == "name: alpha\nversion: 1.2.4\n"
    assert (repo / "src/plugins/beta/plugin.yaml").read_text() == "name: beta\nversion: 0.4.8\n"
    assert (repo / "README.md").read_text() == "| **alpha** | 1.2.4 | a |\n| **beta** | 0.4.8 | b |\nHistorical nstack 0.0.6.\n"
    assert (repo / "src/plugins/alpha/README.md").read_text() == "# alpha\n\nVersion: **1.2.4**\n\nHistorical 0.0.6 and pstack 0.15.30.\n"
    assert (repo / "CHANGELOG.md").read_bytes().split(r.BOUNDARY)[1] == legacy
    assert b"## [alpha 1.2.4] -" in (repo / "CHANGELOG.md").read_bytes()


def test_none_resolution_persists_without_tag_or_version(repo):
    sha = change(repo, "unknown wording")
    decision = r.Decision("alpha", sha, "none", "No shipped behavior change.")
    plan = r.propose(repo, (decision,)).plan
    assert (plan["state"], plan["releases"], plan["requests"]) == ("ReadyPlan", [], [])
    r.prepare(repo, plan)
    commit(repo, "chore(release): record reviewed exclusions")
    result = r.propose(repo, (decision,))
    assert isinstance(result, r.NoChanges)
    next_sha = change(repo, "another unknown")
    result = r.propose(repo, (decision,))
    assert [row["commit"] for row in result.plan["requests"]] == [next_sha]


def test_unrelated_resolution_fails(repo):
    sha = change(repo, "fix(alpha): known")
    with pytest.raises(r.ReleaseError, match="Stale"):
        r.propose(repo, (r.Decision("beta", sha, "none", "Unrelated."),))


def test_accepted_none_cannot_be_removed_or_rebound(repo):
    sha = change(repo, "unknown wording")
    decision = r.Decision("alpha", sha, "none", "Reviewed exclusion.")
    r.prepare(repo, r.propose(repo, (decision,)).plan)
    commit(repo, "chore(release): exclusions")
    with pytest.raises(r.ReleaseError, match="Accepted decision"):
        r.propose(repo, ())
    with pytest.raises(r.ReleaseError, match="Accepted decision"):
        r.propose(repo, (r.Decision("alpha", sha, "patch", "Changed mind without a new transaction."),))


def test_incomplete_transaction_and_version_rollback_are_not_hidden(repo):
    source = repo / "src/plugins/alpha/plugin.yaml"
    source.write_text("name: alpha\nversion: 1.2.9\n")
    commit(repo, "fix(alpha): manual bump")
    source.write_text("name: alpha\nversion: 1.2.3\n")
    commit(repo, "fix(alpha): revert manual bump")
    with pytest.raises(r.ReleaseError, match="manual source version"):
        r.propose(repo)


def test_blocked_plan_cannot_be_accepted_as_completed_history(repo):
    change(repo, "unknown wording")
    r.prepare(repo, r.propose(repo).plan)
    commit(repo, "chore(release): invalid unresolved merge")
    with pytest.raises(r.ReleaseError, match="Incomplete prior release transaction"):
        r.propose(repo)
    result = subprocess.run([sys.executable, str(ROOT / "tools/release.py"), "check", "--root", str(repo)],
                            text=True, capture_output=True)
    assert result.returncode == 1
    assert "Unanswered release decisions" in result.stderr


def test_manual_version_changes_fail_in_planner_and_cli(repo):
    write(repo, "src/plugins/beta/plugin.yaml", "name: beta\nversion: 0.4.9\n")
    commit(repo, "docs: unreviewed manual bump")
    with pytest.raises(r.ReleaseError, match="Unexplained manual version change for beta"):
        r.propose(repo)
    result = subprocess.run([sys.executable, str(ROOT / "tools/release.py"), "check", "--root", str(repo)],
                            text=True, capture_output=True)
    assert result.returncode == 1
    assert "Unexplained manual version change for beta" in result.stderr


def test_removing_source_identity_fails_instead_of_inventing_current_version(repo):
    (repo / "src/plugins/alpha/plugin.yaml").unlink()
    commit(repo, "feat(alpha)!: remove plugin identity")
    with pytest.raises(r.ReleaseError, match="Removed component requires an explicit migration"):
        r.propose(repo)


def test_actual_prepare_cli_buildkit_and_bundle(repo):
    from buildkit.build import build, check
    for name in ("alpha", "beta"):
        source = repo / f"src/plugins/{name}/plugin.yaml"
        source.write_text(source.read_text() + "description: Test fixture.\n")
        write(repo, f"src/plugins/{name}/skills/one/SKILL.md.j2",
              "---\nname: one\ndescription: A fixture skill.\ntargets: [claude, copilot, codex]\n---\n\nOriginal guidance.\n")
    anchor = commit(repo, "chore: valid shipping fixture sources")
    write(repo, ".release/baselines.toml",
          f'[baseline]\nalpha = "{anchor}"\nbeta = "{anchor}"\nnilpath-marketplace = "{anchor}"\n')
    build(repo)
    commit(repo, "ci: accept shipping fixture baseline")
    write(repo, "src/plugins/alpha/skills/one/SKILL.md.j2",
          (repo / "src/plugins/alpha/skills/one/SKILL.md.j2").read_text() + "\nRepaired guidance.\n")
    build(repo)
    sha = commit(repo, "fix(alpha): repair guidance")
    req = request(sha)
    request_path = repo.parent / (repo.name + "-request.json")
    request_path.write_bytes(r.canonical(req))
    result = subprocess.run([sys.executable, str(ROOT / "tools/release.py"), "prepare", "--root", str(repo),
                             "--request", str(request_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["releases"][0]["target"] == "1.2.4"
    assert check(repo) != []
    build(repo)
    assert check(repo) == []
    bundle = r.bundle(repo, req)
    files = r.validate_artifact(bundle)
    for harness, manifest in (("claude", ".claude-plugin/plugin.json"), ("copilot", "plugin.json"),
                              ("codex", ".codex-plugin/plugin.json")):
        path = f"dist/{harness}/plugins/alpha/{manifest}"
        assert json.loads(files[path])["version"] == "1.2.4"
        beta = json.loads((repo / f"dist/{harness}/plugins/beta/{manifest}").read_text())
        assert beta["version"] == "0.4.8"
    assert files["dist/codex/plugins/alpha/README.md"].startswith(b"# alpha\n\nVersion: **1.2.4**")
    assert bundle["plan"]["releases"][0]["commits"] == [sha]
    commit(repo, "chore(release): accepted preparation")
    result = subprocess.run([sys.executable, str(ROOT / "tools/release.py"), "check", "--root", str(repo)],
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert isinstance(r.propose(repo), r.NoChanges)
    beta_skill = repo / "src/plugins/beta/skills/one/SKILL.md.j2"
    beta_skill.write_text(beta_skill.read_text() + "\nBeta repair.\n")
    build(repo)
    beta_sha = commit(repo, "fix(beta): independent follow-up")
    plan = r.propose(repo).plan
    assert [(item["component"], item["current"], item["target"], item["commits"]) for item in plan["releases"]] == [
        ("beta", "0.4.8", "0.4.9", [beta_sha])]


def test_wrong_readme_selector_fails(repo):
    change(repo, "fix(alpha): known")
    plan = r.propose(repo).plan
    originals = r.tracked_originals(repo, plan, plan["input_sha"])
    originals["README.md"] = b"| **alpha** | 1.0.0 | wrong |\n"
    with pytest.raises(r.ReleaseError, match="README"):
        r.expected_updates(plan, originals)


def test_two_releases_prepend_notes_and_preserve_every_legacy_byte(repo):
    legacy = (repo / "CHANGELOG.md").read_bytes().split(r.BOUNDARY)[1]
    change(repo, "fix(alpha): first repair")
    r.prepare(repo, r.propose(repo).plan)
    commit(repo, "chore(release): first release")
    change(repo, "fix(alpha): second repair")
    r.prepare(repo, r.propose(repo).plan)
    notes = (repo / "CHANGELOG.md").read_bytes()
    assert notes.index(b"## [alpha 1.2.5]") < notes.index(b"## [alpha 1.2.4]")
    assert notes.count(b"First repair") == notes.count(b"Second repair") == 1
    assert notes.split(r.BOUNDARY)[1] == legacy


@pytest.mark.parametrize("conventional", [True, False])
def test_notes_use_safe_subjects_without_losing_commits(repo, conventional):
    subject = ("fix(alpha): " if conventional else "") + "Retain <!-- release-legacy-boundary --> and <!-- nilpath-release:subject -->"
    sha = change(repo, subject + "\n\n<!-- release-legacy-boundary -->\n<!-- nilpath-release:body -->\nPrivate body text.")
    decisions = () if conventional else (r.Decision("alpha", sha, "patch", "Reviewed subject."),)
    plan = r.propose(repo, decisions).plan
    notes = plan["releases"][0]["notes"]
    assert "Retain &lt;!-- release-legacy-boundary --&gt; and &lt;!-- nilpath-release:subject --&gt;" in notes
    assert sha in notes
    assert "Private body" not in notes and "nilpath-release:body" not in notes
    r.prepare(repo, plan)
    assert (repo / "CHANGELOG.md").read_bytes().count(r.BOUNDARY) == 1


def test_historical_plan_survives_tool_upgrade_but_new_contract_does_not(repo, monkeypatch):
    change(repo, "fix(alpha): released")
    plan = r.propose(repo).plan
    r.prepare(repo, plan)
    released = commit(repo, "chore(release): completed preparation")
    monkeypatch.setattr(r, "CLIFF_VERSION", "2.14.0")
    assert r.previous_transactions(repo)[0][0] == released
    assert r.main(["check", "--root", str(repo)]) == 0
    assert isinstance(r.propose(repo), r.NoChanges)
    with pytest.raises(r.ReleaseError, match="Unsupported current tools"):
        r.validate_current_plan(plan)
    plan["schema"] = 2
    with pytest.raises(r.ReleaseError, match="Unsupported plan schema"):
        r.validate_plan(plan)


def test_schema1_bytes_survive_current_updater_changes_but_new_bytes_require_schema_repair(repo, monkeypatch):
    change(repo, "fix(alpha): repair")
    plan = r.propose(repo).plan
    originals = r.tracked_originals(repo, plan, plan["input_sha"])
    expected = r.expected_updates(plan, originals)
    monkeypatch.setattr(r, "changelog_update", lambda raw, plan: b"New incompatible changelog\n")
    assert r.historical_updates(plan, originals) == expected
    with pytest.raises(r.ReleaseError, match="schema-1 byte contract"):
        r.prepare(repo, plan)
    assert not (repo / ".release/plan.json").exists()


@pytest.mark.parametrize("bad", ["tool", "policy", "digest"])
def test_historical_updates_require_original_tool_and_policy_identities(repo, bad):
    change(repo, "fix(alpha): repair")
    plan = r.propose(repo).plan
    originals = r.tracked_originals(repo, plan, plan["input_sha"])
    if bad == "tool":
        plan["tool_versions"]["git-cliff"] = "2.14.0"
    elif bad == "policy":
        plan["tool_versions"]["policy"] = "2"
    else:
        plan["policy_digest"] = "f" * 64
    plan["plan_id"] = r.digest(r.canonical({k: v for k, v in plan.items() if k != "plan_id"}))
    with pytest.raises(r.ReleaseError, match="Historical tool identity|Unsupported historical policy|policy digest"):
        r.historical_updates(plan, originals)


@pytest.mark.parametrize("decision_only", [True, False])
@pytest.mark.parametrize("committed", [True, False])
def test_check_rejects_deleted_plan_for_all_transaction_kinds(repo, decision_only, committed):
    sha = change(repo, "unknown wording" if decision_only else "fix(alpha): release")
    decisions = (r.Decision("alpha", sha, "none", "Reviewed exclusion."),) if decision_only else ()
    r.prepare(repo, r.propose(repo, decisions).plan)
    commit(repo, "chore(release): accepted")
    (repo / ".release/plan.json").unlink()
    if committed:
        commit(repo, "chore: delete provenance")
    result = subprocess.run([sys.executable, str(ROOT / "tools/release.py"), "check", "--root", str(repo)],
                            text=True, capture_output=True)
    assert result.returncode == 1
    assert "Prior transaction was removed" in result.stderr


@pytest.mark.parametrize("bad", [None, "extra", "update", "stale", "rebase", "mode"])
def test_actual_proposal_cli_checks_exact_head_parent_base_and_tree(repo, bad):
    change(repo, "fix(alpha): repair")
    plan = r.propose(repo).plan
    r.prepare(repo, plan)
    if bad == "extra":
        write(repo, "unrelated.txt", "Not a release edit.")
    commit(repo, "chore(release): proposal")
    if bad == "update":
        write(repo, "unrelated.txt", "Added after generation.")
        commit(repo, "chore: extra proposal commit")
    elif bad == "rebase":
        original_tree = command(repo, "git", "rev-parse", "HEAD^{tree}")
        new_base = command(repo, "git", "-c", "user.name=Tester", "-c", "user.email=test@example.com",
                           "commit-tree", command(repo, "git", "rev-parse", plan["input_sha"] + "^{tree}"),
                           "-p", plan["input_sha"], "-m", "New main")
        rewritten = command(repo, "git", "-c", "user.name=Tester", "-c", "user.email=test@example.com",
                            "commit-tree", original_tree, "-p", new_base, "-m", "Rebased proposal")
        command(repo, "git", "reset", "--hard", rewritten)
    elif bad == "mode":
        command(repo, "git", "update-index", "--chmod=+x", "README.md")
        command(repo, "git", "-c", "user.name=Tester", "-c", "user.email=test@example.com",
                "commit", "--amend", "--no-edit", "-q")
    base = "a" * 40 if bad == "stale" else plan["input_sha"]
    result = subprocess.run([sys.executable, str(ROOT / "tools/release.py"), "check-proposal",
                             "--root", str(repo), "--base-sha", base], text=True, capture_output=True)
    assert result.returncode == (0 if bad is None else 1), result.stderr
    if bad is None:
        assert result.stdout == "Exact proposal checks passed.\n"


@pytest.mark.parametrize("args,missing", [
    (["snapshot"], "--output"),
    (["write"], "--artifact"),
    (["prepare"], "--request"),
    (["bundle"], "--request"),
    (["bundle", "--request", "absent.json"], "--output"),
    (["check-proposal"], "--base-sha"),
])
def test_cli_requires_arguments_before_environment_or_repository_access(tmp_path, args, missing):
    result = subprocess.run(
        [sys.executable, "-S", str(ROOT / "tools/release.py"), *args],
        cwd=tmp_path, env={}, text=True, capture_output=True,
    )
    assert result.returncode == 2
    assert f"the following arguments are required: {missing}" in result.stderr
    assert result.stdout == ""
    assert list(tmp_path.iterdir()) == []


def test_make_supplies_declared_git_cliff_without_global_path(tmp_path):
    target = tmp_path / "renderer.mk"
    target.write_text("verify-renderer:\n\t$(PYTHON) -c 'import subprocess; subprocess.run([\"git-cliff\", \"--version\"], check=True)'\n")
    result = subprocess.run(
        ["/usr/bin/make", "-f", str(ROOT / "Makefile"), "-f", str(target),
         "verify-renderer", f"VENV={sys.prefix}"],
        cwd=ROOT, env={**os.environ, "PATH": "/usr/bin:/bin"}, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "git-cliff 2.13.1" in result.stdout.splitlines()


def test_writer_creates_exact_draft_pr_and_retries_without_rewriting(prepared):
    _, gh, artifact = prepared
    assert r.create_proposal(gh, artifact) == 1
    pr = gh.prs[1]
    assert pr["draft"] is True
    assert pr["head"]["ref"].startswith("release/proposal-")
    source = gh.content(gh.tree(pr["head"]["sha"]), "src/plugins/alpha/plugin.yaml")
    assert source == b"name: alpha\nversion: 1.2.4\n"
    writes = copy.deepcopy(gh.writes)
    assert r.create_proposal(gh, artifact) == 1
    assert gh.writes == writes


@pytest.mark.parametrize("path,mode", [
    ("../escape", "100644"), ("/tmp/escape", "100644"), ("src//bad", "100644"),
    (".", "100644"), ("C:/escape", "100644"), ("src\\evil", "100644"),
    ("src/plugins/alpha/hooks/evil.py", "100644"), ("README.md", "120000"),
    (".github/workflows/ci.yml", "100644"),
])
def test_malicious_artifact_never_reaches_mutation(prepared, path, mode):
    _, gh, artifact = prepared
    artifact["files"].append({"path": path, "mode": mode, "content": "ZXZpbA==", "sha256": r.digest(b"evil")})
    artifact["digest"] = r.digest(r.canonical({k: v for k, v in artifact.items() if k != "digest"}))
    with pytest.raises(r.ReleaseError):
        r.create_proposal(gh, artifact)
    assert gh.writes == []


def test_corrupt_artifact_and_duplicate_json_fields_fail_closed(prepared):
    _, gh, artifact = prepared
    artifact["files"][0]["content"] = "ZXZpbA=="
    with pytest.raises(r.ReleaseError, match="digest"):
        r.create_proposal(gh, artifact)
    with pytest.raises(r.ReleaseError, match="Duplicate"):
        r.load_json(b'{"x":1,"x":2}')
    assert gh.writes == []


def test_stale_input_and_symlink_source_fail_closed(prepared):
    _, gh, artifact = prepared
    old = gh.main
    gh.main = "a" * 40
    with pytest.raises(r.ReleaseError, match="Stale"):
        r.create_proposal(gh, artifact)
    gh.main = old
    gh.trees[old]["src/plugins/alpha/plugin.yaml"]["mode"] = "120000"
    with pytest.raises(r.ReleaseError, match="Unsafe mode"):
        r.create_proposal(gh, artifact)
    assert gh.writes == []


@pytest.mark.parametrize("run_id,attempt", [("42", "1"), ("42", "2"), ("99", "1")])
def test_pr_creation_retry_reuses_transaction_branch(prepared, run_id, attempt):
    root, gh, artifact = prepared
    gh.fail = "pulls"
    with pytest.raises(r.ReleaseError, match="Injected"):
        r.create_proposal(gh, artifact)
    retry = r.bundle(root, {**artifact["request"], "run_id": run_id, "run_attempt": attempt})
    assert r.create_proposal(gh, retry) == 1
    assert list(gh.refs) == ["refs/heads/release/proposal-" + artifact["plan"]["plan_id"]]
    assert len([w for w in gh.writes if w[0] == "git/refs"]) == 1


def reviewed_fixture(prepared, number=1):
    _, gh, artifact = prepared
    assert r.create_proposal(gh, artifact) == number
    pr = gh.prs[number]
    head = pr["head"]["sha"]
    merged = "e" * 40
    gh.commits[merged] = copy.deepcopy(gh.commits[head])
    gh.commits[merged]["sha"] = merged
    gh.trees[merged] = gh.trees[head]
    pr.update({"merged": True, "state": "closed", "draft": False, "merge_commit_sha": merged})
    gh.routes[f"pulls/{number}/reviews?per_page=100&page=1"] = [{
        "id": 1, "state": "APPROVED", "commit_id": head, "user": {"id": 8, "type": "User"},
        "author_association": "OWNER",
    }]
    gh.routes["actions/workflows/ci.yml"] = {"id": 50, "path": ".github/workflows/ci.yml"}
    run_path = "actions/workflows/ci.yml/runs?" + urlencode({"head_sha": head, "event": "pull_request"}) + "&per_page=100&page=1"
    gh.routes[run_path] = {"total_count": 1, "workflow_runs": [{
        "id": 70, "run_attempt": 2, "head_sha": head, "workflow_id": 50, "event": "pull_request",
        "path": ".github/workflows/ci.yml", "head_repository": {"full_name": gh.repository},
        "pull_requests": [], "status": "completed", "conclusion": "success", "check_suite_id": 90,
    }]}
    gh.routes[f"commits/{head}/pulls?per_page=100&page=1"] = [copy.deepcopy(pr)]
    jobs = [{"id": 100 + i, "name": name, "head_sha": head, "status": "completed",
             "conclusion": "success", "html_url": f"https://github.com/nilpath/test/actions/runs/70/job/{100+i}"}
            for i, name in enumerate(("test-static", "release-plan"))]
    gh.routes["actions/runs/70/attempts/2/jobs?per_page=100&page=1"] = {"total_count": 2, "jobs": jobs}
    checks = [{"id": 200 + i, "name": job["name"], "head_sha": head, "app": {"id": r.ACTIONS_APP_ID},
               "details_url": job["html_url"], "check_suite": {"id": 90}, "conclusion": "success"}
              for i, job in enumerate(jobs)]
    gh.routes[f"commits/{head}/check-runs?filter=latest&per_page=100&page=1"] = {"total_count": 2, "check_runs": checks}
    return gh, artifact["plan"], merged, head


def test_exact_review_merge_and_check_provenance(prepared):
    gh, plan, merged, head = reviewed_fixture(prepared)
    reviewed = r.reviewed_release(gh, 1, merged, plan)
    assert (reviewed.merged_sha, reviewed.head_sha, reviewed.plan["releases"][0]["target"]) == (merged, head, "1.2.4")
    writes = copy.deepcopy(gh.writes)
    with pytest.raises(r.ReleaseError, match="Incomplete prior"):
        r.reconcile_drafts(gh, reviewed, create=False)
    assert gh.writes == writes
    r.reconcile_drafts(gh, reviewed)
    assert gh.tags == {"alpha/v1.2.4": {"type": "commit", "sha": merged}}
    assert gh.releases[0]["draft"] is True
    assert gh.releases[0]["target_commitish"] == merged
    assert r.release_marker(plan["releases"][0], merged, plan["plan_id"]) in gh.releases[0]["body"]
    writes = copy.deepcopy(gh.writes)
    gh.releases[0]["body"] += "\nHuman release notes."
    r.reconcile_drafts(gh, reviewed)
    gh.releases[0]["draft"] = False
    r.reconcile_drafts(gh, reviewed)
    r.reconcile_drafts(gh, reviewed, create=False)
    assert gh.writes == writes
    assert gh.releases[0]["body"].endswith("Human release notes.")


@pytest.mark.parametrize("bad", ["parent", "tree", "review", "run", "job", "app", "suite", "details",
                               "association", "association-head", "association-repo", "workflow", "run-repo"])
def test_invalid_release_provenance_is_visible_failure(prepared, bad):
    gh, plan, merged, head = reviewed_fixture(prepared)
    if bad == "parent":
        gh.commits[merged]["parents"] = [{"sha": "a" * 40}]
    elif bad == "tree":
        gh.commits[merged]["tree"]["sha"] = "a" * 40
    elif bad == "review":
        gh.routes["pulls/1/reviews?per_page=100&page=1"][0]["commit_id"] = "a" * 40
    elif bad == "run":
        path = next(p for p in gh.routes if "/runs?" in p)
        gh.routes[path]["workflow_runs"][0]["head_sha"] = "a" * 40
    elif bad.startswith("association"):
        association = gh.routes[f"commits/{head}/pulls?per_page=100&page=1"]
        if bad == "association":
            association.clear()
        elif bad == "association-head":
            association[0]["head"]["sha"] = "a" * 40
        else:
            association[0]["head"]["repo"]["full_name"] = "attacker/fork"
    elif bad in {"workflow", "run-repo"}:
        path = next(p for p in gh.routes if "/runs?" in p)
        run = gh.routes[path]["workflow_runs"][0]
        if bad == "workflow":
            run["workflow_id"] = 1
        else:
            run["head_repository"]["full_name"] = "attacker/fork"
    elif bad == "job":
        gh.routes["actions/runs/70/attempts/2/jobs?per_page=100&page=1"]["jobs"][0]["conclusion"] = "failure"
    else:
        checks = gh.routes[f"commits/{head}/check-runs?filter=latest&per_page=100&page=1"]["check_runs"]
        if bad == "app":
            checks[0]["app"]["id"] = 1
        elif bad == "suite":
            checks[0]["check_suite"]["id"] = 1
        else:
            checks[0]["details_url"] = "https://example.com/spoofed"
    writes = len(gh.writes)
    with pytest.raises(r.ReleaseError):
        r.reviewed_release(gh, 1, merged, plan)
    assert len(gh.writes) == writes


def test_draft_partial_failure_and_conflicting_objects(prepared):
    gh, plan, merged, head = reviewed_fixture(prepared)
    reviewed = r.reviewed_release(gh, 1, merged, plan)
    gh.fail = "release-create"
    with pytest.raises(r.ReleaseError, match="Injected"):
        r.reconcile_drafts(gh, reviewed)
    assert gh.tags == {"alpha/v1.2.4": {"type": "commit", "sha": merged}}
    r.reconcile_drafts(gh, reviewed)
    assert len(gh.releases) == 1
    assert len([w for w in gh.writes if w[0] == "git/refs" and w[1]["ref"].startswith("refs/tags/")]) == 1
    gh.tags["alpha/v1.2.4"]["sha"] = "a" * 40
    with pytest.raises(r.ReleaseError, match="Conflicting tag"):
        r.reconcile_drafts(gh, reviewed)
    gh.tags["alpha/v1.2.4"]["sha"] = merged
    gh.releases[0]["body"] = "Unowned human release"
    gh.releases[0]["draft"] = False
    with pytest.raises(r.ReleaseError, match="unowned"):
        r.reconcile_drafts(gh, reviewed)


@pytest.mark.parametrize("failure", [None, "issues/1/comments", "pulls/1"])
def test_resolution_reads_only_expected_head_and_keeps_old_pr_until_replacement(repo, failure):
    sha = change(repo, "unknown wording")
    gh = FakeGitHub(repo)
    blocked = r.propose(repo).plan
    r.prepare(repo, blocked)
    artifact = r.bundle(repo, request(blocked["input_sha"]))
    r.create_proposal(gh, artifact)
    old_head = gh.prs[1]["head"]["sha"]
    decision = r.Decision("alpha", sha, "none", "Reviewed exclusion.")
    edited_head = "b" * 40
    edit_proposal_decisions(gh, (decision,), edited_head)
    with pytest.raises(r.ReleaseError, match="Stale resolution"):
        r.snapshot(gh, mode="prepare", proposal_pr=1, expected_head=old_head, merged_sha=None,
                   event_sha=gh.main, identity=IDENTITY)
    snapshot = r.snapshot(gh, mode="prepare", proposal_pr=1, expected_head=edited_head, merged_sha=None,
                          event_sha=gh.main, identity=IDENTITY)
    assert snapshot["decisions"] == [decision.__dict__]
    assert snapshot["expected_head"] == edited_head
    r.prepare(repo, r.propose(repo, (decision,)).plan)
    req = request(gh.main, proposal_pr=1, expected_head=edited_head, decisions=[decision.__dict__])
    resolved = r.bundle(repo, req)
    if failure:
        gh.fail = failure
        with pytest.raises(r.ReleaseError, match="Injected"):
            r.create_proposal(gh, resolved)
        assert gh.prs[1]["state"] == "open"
        assert gh.prs[2]["draft"] is True
    assert r.create_proposal(gh, resolved) == 2
    assert gh.prs[1]["state"] == "closed"
    assert gh.prs[2]["draft"] is True
    assert gh.tags == {}
    assert gh.prs[1]["head"]["sha"] == edited_head
    post_positions = [(i, s) for i, (s, _) in enumerate(gh.writes)]
    new_pr = max(i for i, s in post_positions if s == "pulls")
    old_close = max(i for i, s in post_positions if s == "pulls/1")
    assert new_pr < old_close


class Response(io.BytesIO):
    status = 200


class Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        item = next(self.responses)
        if isinstance(item, Exception):
            raise item
        return Response(json.dumps(item).encode())


def test_real_transport_complete_pagination_and_failure_boundary():
    opener = Opener([[{"id": i} for i in range(100)], [{"id": 100}]])
    gh = r.GitHub("nilpath/test", "fake", opener)
    assert [row["id"] for row in gh.pages("releases")] == list(range(101))
    assert opener.requests[1].full_url == "https://api.github.com/repos/nilpath/test/releases?per_page=100&page=2"
    for failure in (HTTPError("url", 404, "not found", {}, None), HTTPError("url", 403, "forbidden", {}, None), URLError("offline")):
        gh = r.GitHub("nilpath/test", "fake", Opener([failure]))
        with pytest.raises(r.ReleaseError):
            gh.pages("releases")
    gh = r.GitHub("nilpath/test", "fake", Opener([{"total_count": 2, "jobs": [{"id": 1}]}]))
    with pytest.raises(r.ReleaseError, match="Incomplete"):
        gh.pages("actions/runs/1/jobs", "jobs")
    failure = HTTPError("url", 500, "unavailable", {}, None)
    gh = r.GitHub("nilpath/test", "fake", Opener([[{"id": i} for i in range(100)], failure]))
    with pytest.raises(r.ReleaseError, match="500"):
        gh.pages("releases")


def test_dispatch_binds_drafts_to_reviewed_merge_instead_of_current_main(prepared):
    gh, plan, merged, head = reviewed_fixture(prepared)
    gh.main = "a" * 40
    req = r.snapshot(gh, mode="drafts", proposal_pr=1, merged_sha=merged, expected_head=None,
                     event_sha=gh.main, identity=IDENTITY)
    assert (req["kind"], req["input_sha"], req["merged_sha"], req["expected_head"]) == (
        "drafts", merged, merged, head)
    gh.main = "a" * 40
    gh.routes[f"commits/{merged}/pulls?per_page=100&page=1"] = [gh.prs[1]]
    req = r.snapshot(gh, mode="auto", proposal_pr=None, merged_sha=None, expected_head=None,
                     event_sha=merged, identity=IDENTITY)
    assert (req["kind"], req["proposal_pr"], req["merged_sha"]) == ("drafts", 1, merged)
    gh.routes["commits/" + "f" * 40 + "/pulls?per_page=100&page=1"] = []
    with pytest.raises(r.ReleaseError, match="no longer main"):
        r.snapshot(gh, mode="auto", proposal_pr=None, merged_sha=None, expected_head=None,
                   event_sha="f" * 40, identity=IDENTITY)
    gh.prs[1]["body"] = "Broken recognized release metadata"
    with pytest.raises(r.ReleaseError, match="ownership marker"):
        r.snapshot(gh, mode="auto", proposal_pr=None, merged_sha=None, expected_head=None,
                   event_sha=merged, identity=IDENTITY)


def test_matching_published_release_with_conflicting_marker_is_not_adopted(prepared):
    gh, plan, merged, head = reviewed_fixture(prepared)
    reviewed = r.reviewed_release(gh, 1, merged, plan)
    r.reconcile_drafts(gh, reviewed)
    gh.releases[0]["draft"] = False
    gh.releases[0]["body"] += "\n<!-- nilpath-release:other:1.0.0:" + "f" * 40 + ":" + "f" * 64 + " -->"
    with pytest.raises(r.ReleaseError, match="unowned"):
        r.reconcile_drafts(gh, reviewed)


@pytest.mark.parametrize("bad", ["moved-tag", "extra-marker", "wrong-marker", "wrong-title", "published", "prerelease", "id"])
def test_created_release_is_rechecked_after_mutation(prepared, monkeypatch, bad):
    gh, plan, merged, _ = reviewed_fixture(prepared)
    reviewed = r.reviewed_release(gh, 1, merged, plan)
    create = gh.release_create

    def raced_create(*args):
        create(*args)
        release = gh.releases[0]
        if bad == "moved-tag":
            gh.tags["alpha/v1.2.4"]["sha"] = "a" * 40
        elif bad == "extra-marker":
            release["body"] += "\n" + r.release_marker(plan["releases"][0], merged, plan["plan_id"])
        elif bad == "wrong-marker":
            release["body"] = "<!-- nilpath-release:other:1.0.0:" + merged + ":" + plan["plan_id"] + " -->"
        elif bad == "wrong-title":
            release["name"] = "other 9.0.0"
        elif bad == "published":
            release["draft"] = False
        elif bad == "prerelease":
            release["prerelease"] = True
        else:
            release["id"] = None

    monkeypatch.setattr(gh, "release_create", raced_create)
    with pytest.raises(r.ReleaseError):
        r.reconcile_drafts(gh, reviewed)


def test_actual_tag_is_authority_not_unused_target_commitish(prepared):
    gh, plan, merged, _ = reviewed_fixture(prepared)
    reviewed = r.reviewed_release(gh, 1, merged, plan)
    r.reconcile_drafts(gh, reviewed)
    gh.releases[0]["target_commitish"] = "main"
    gh.releases[0]["body"] += "\nHuman release text."
    writes = copy.deepcopy(gh.writes)
    r.reconcile_drafts(gh, reviewed)
    assert gh.writes == writes
    assert gh.releases[0]["body"].endswith("Human release text.")
    gh.tags["alpha/v1.2.4"]["sha"] = "a" * 40
    with pytest.raises(r.ReleaseError, match="Conflicting tag"):
        r.reconcile_drafts(gh, reviewed)


def set_prior_history(gh, input_sha, merged):
    gh.routes["commits?" + urlencode({"sha": input_sha, "path": ".release/plan.json"})
              + "&per_page=100&page=1"] = [{"sha": merged}]
    gh.routes[f"commits/{merged}/pulls?per_page=100&page=1"] = [
        copy.deepcopy(p) for p in gh.prs.values() if p.get("merge_commit_sha") == merged]


def test_completed_receipts_survive_missing_ci_and_changed_updater(prepared, monkeypatch):
    gh, plan, merged, _ = reviewed_fixture(prepared)
    r.reconcile_drafts(gh, r.reviewed_release(gh, 1, merged, plan))
    set_prior_history(gh, merged, merged)
    for path in list(gh.routes):
        if path.startswith("actions/") or "/check-runs" in path or "/reviews?" in path:
            gh.routes[path] = r.ReleaseError("CI record deleted")

    def changed_updater(*args):
        raise AssertionError("Historical content must not be rerendered")

    monkeypatch.setattr(r, "expected_updates", changed_updater)
    monkeypatch.setattr(r, "CLIFF_VERSION", "2.14.0")
    reviewed = r.reviewed_release(gh, 1, merged, plan)
    r.prior_complete(gh, merged)
    writes = copy.deepcopy(gh.writes)
    r.reconcile_drafts(gh, reviewed)
    assert gh.writes == writes
    assert gh.releases[0]["tag_name"] == "alpha/v1.2.4"


def test_first_draft_still_requires_ci_and_incomplete_history_blocks(prepared):
    gh, plan, merged, _ = reviewed_fixture(prepared)
    gh.routes["actions/workflows/ci.yml"] = r.ReleaseError("CI record deleted")
    with pytest.raises(r.ReleaseError, match="CI record deleted"):
        r.reviewed_release(gh, 1, merged, plan)
    set_prior_history(gh, merged, merged)
    with pytest.raises(r.ReleaseError, match="Incomplete prior"):
        r.prior_complete(gh, merged)


@pytest.mark.parametrize("decision_only", [True, False])
def test_remote_history_cannot_be_hidden_by_deleting_active_plan(repo, decision_only):
    sha = change(repo, "unknown wording" if decision_only else "fix(alpha): repair")
    decisions = (r.Decision("alpha", sha, "none", "Reviewed exclusion."),) if decision_only else ()
    gh = FakeGitHub(repo)
    if decisions:
        blocked = r.propose(repo).plan
        r.prepare(repo, blocked)
        r.create_proposal(gh, r.bundle(repo, request(gh.main)))
        edit_proposal_decisions(gh, decisions)
    plan = r.propose(repo, decisions).plan
    r.prepare(repo, plan)
    req = request(gh.main, decisions=[d.__dict__ for d in decisions],
                  proposal_pr=1 if decisions else None, expected_head="b" * 40 if decisions else None)
    artifact = r.bundle(repo, req)
    number = 2 if decisions else 1
    gh, plan, merged, _ = reviewed_fixture((repo, gh, artifact), number)
    r.reconcile_drafts(gh, r.reviewed_release(gh, number, merged, plan))
    set_prior_history(gh, merged, merged)
    gh.routes["actions/workflows/ci.yml"] = r.ReleaseError("CI record deleted")
    r.prior_complete(gh, merged)
    assert len(gh.releases) == (0 if decision_only else 1)
    later = "c" * 40
    gh.trees[later] = copy.deepcopy(gh.trees[merged])
    del gh.trees[later][".release/plan.json"]
    set_prior_history(gh, later, merged)
    with pytest.raises(r.ReleaseError, match="Prior transaction was removed"):
        r.prior_complete(gh, later)


def edit_proposal_decisions(gh, decisions, head="b" * 40):
    tree = copy.deepcopy(gh.trees[gh.prs[1]["head"]["sha"]])
    raw = r.decisions_bytes(decisions)
    sha = blob_sha(raw)
    gh.blobs[sha] = raw
    tree[".release/decisions.toml"] = {"mode": "100644", "type": "blob", "path": ".release/decisions.toml", "sha": sha}
    gh.trees[head] = tree
    gh.prs[1]["head"]["sha"] = head


def snapshot_prepare(gh):
    return r.snapshot(gh, mode="prepare", proposal_pr=None, expected_head=None, merged_sha=None,
                      event_sha=gh.main, identity=IDENTITY)


def advance_main(root, gh):
    prior_plan = r.blob(root, gh.main, ".release/plan.json", optional=True)
    command(root, "git", "reset", "--hard", gh.main)
    if prior_plan is None:
        (root / ".release/plan.json").unlink(missing_ok=True)
    change(root, "docs: independent repository note", path="README-extra.md", name="beta")
    gh.main = command(root, "git", "rev-parse", "HEAD")
    gh.load_commit(gh.main)


@pytest.mark.parametrize("failure", ["issues/1/comments", "pulls/1"])
@pytest.mark.parametrize("new_main", [False, True])
def test_automatic_supersession_recovers_two_active_prs_after_new_attempt(prepared, failure, new_main):
    root, gh, artifact = prepared
    r.create_proposal(gh, artifact)
    gh.prs[1]["draft"] = False
    advance_main(root, gh)
    req = snapshot_prepare(gh)
    r.prepare(root, r.propose(root, r.decisions_from_data(req["decisions"])).plan)
    refreshed = r.bundle(root, req)
    gh.fail = failure
    with pytest.raises(r.ReleaseError, match="Injected"):
        r.create_proposal(gh, refreshed)
    assert [(p["number"], p["state"]) for p in gh.prs.values()] == [(1, "open"), (2, "open")]
    if new_main:
        advance_main(root, gh)
    retry = snapshot_prepare(gh)
    retry["run_attempt"] = "2"
    if new_main:
        r.prepare(root, r.propose(root, r.decisions_from_data(retry["decisions"])).plan)
    assert r.create_proposal(gh, r.bundle(root, retry)) == (3 if new_main else 2)
    assert [(p["number"], p["state"]) for p in gh.prs.values()] == (
        [(1, "closed"), (2, "closed"), (3, "open")] if new_main else [(1, "closed"), (2, "open")])
    assert len([w for w in gh.writes if w[0] == "pulls"]) == (3 if new_main else 2)


def test_exact_decisions_survive_main_advance_and_unmerged_regeneration(repo):
    sha = change(repo, "unknown wording")
    gh = FakeGitHub(repo)
    blocked = r.propose(repo).plan
    r.prepare(repo, blocked)
    r.create_proposal(gh, r.bundle(repo, request(gh.main)))
    decision = r.Decision("alpha", sha, "none", "Reviewed exclusion.")
    edit_proposal_decisions(gh, (decision,))
    advance_main(repo, gh)
    with pytest.raises(r.ReleaseError, match="explicit resolution"):
        snapshot_prepare(gh)
    req = r.snapshot(gh, mode="prepare", proposal_pr=1, expected_head="b" * 40, merged_sha=None,
                     event_sha=gh.main, identity=IDENTITY)
    assert req["decisions"] == [decision.__dict__]
    plan = r.propose(repo, r.decisions_from_data(req["decisions"])).plan
    assert plan["state"] == "ReadyPlan"
    assert plan["releases"][0]["component"] == "beta"
    r.prepare(repo, plan)
    assert r.create_proposal(gh, r.bundle(repo, req)) == 2
    advance_main(repo, gh)
    req = snapshot_prepare(gh)
    assert req["proposal_pr"] == 2 and req["decisions"] == [decision.__dict__]
    plan = r.propose(repo, r.decisions_from_data(req["decisions"])).plan
    assert plan["decisions"] == [decision.__dict__]
    assert not any(row["commit"] == sha for row in plan["requests"])


@pytest.mark.parametrize("bad", ["head", "unrelated", "nonancestor", "stale-decision", "conflict"])
def test_carried_decisions_reject_stale_or_conflicting_proposal_state(repo, bad):
    sha = change(repo, "unknown wording")
    gh = FakeGitHub(repo)
    blocked = r.propose(repo).plan
    r.prepare(repo, blocked)
    r.create_proposal(gh, r.bundle(repo, request(gh.main)))
    decision = r.Decision("alpha", sha, "none", "Reviewed exclusion.")
    edit_proposal_decisions(gh, (decision,))
    advance_main(repo, gh)
    if bad == "unrelated":
        gh.trees["b" * 40]["extra.txt"] = {"mode": "100644", "type": "blob", "sha": "f" * 40, "path": "extra.txt"}
    elif bad == "nonancestor":
        gh.routes[f"compare/{blocked['input_sha']}...{gh.main}"] = {
            "status": "diverged", "merge_base_commit": {"sha": "a" * 40}}
    elif bad == "stale-decision":
        edit_proposal_decisions(gh, (r.Decision("alpha", "f" * 40, "none", "Unrelated SHA."),))
    elif bad == "conflict":
        raw = r.decisions_bytes((r.Decision("alpha", sha, "patch", "Main accepted another decision."),))
        blob = blob_sha(raw)
        gh.blobs[blob] = raw
        gh.trees[gh.main][".release/decisions.toml"]["sha"] = blob
    writes = copy.deepcopy(gh.writes)
    with pytest.raises(r.ReleaseError):
        req = r.snapshot(gh, mode="prepare", proposal_pr=1, expected_head="a" * 40 if bad == "head" else "b" * 40,
                         merged_sha=None, event_sha=gh.main, identity=IDENTITY)
        r.propose(repo, r.decisions_from_data(req["decisions"]))
    assert gh.writes == writes


def test_bypassed_unexpected_merged_tree_still_cannot_create_drafts(prepared):
    gh, plan, merged, head = reviewed_fixture(prepared)
    raw = b"Unreviewed source change"
    sha = blob_sha(raw)
    gh.blobs[sha] = raw
    gh.trees[merged]["unrelated.txt"] = {"mode": "100644", "type": "blob", "sha": sha, "path": "unrelated.txt"}
    with pytest.raises(r.ReleaseError, match="unexpected files"):
        r.reviewed_release(gh, 1, merged, plan)
    assert gh.tags == {} and gh.releases == []


def test_supersession_recovery_refuses_original_head_change(prepared):
    root, gh, artifact = prepared
    r.create_proposal(gh, artifact)
    advance_main(root, gh)
    req = snapshot_prepare(gh)
    r.prepare(root, r.propose(root, r.decisions_from_data(req["decisions"])).plan)
    gh.fail = "pulls/1"
    with pytest.raises(r.ReleaseError, match="Injected"):
        r.create_proposal(gh, r.bundle(root, req))
    gh.prs[1]["head"]["sha"] = "a" * 40
    writes = copy.deepcopy(gh.writes)
    with pytest.raises(r.ReleaseError, match="changed original head"):
        snapshot_prepare(gh)
    assert gh.writes == writes


@pytest.mark.parametrize("identity_field,identity_value", [
    ("GITHUB_RUN_ID", "43"),
    ("GITHUB_RUN_ATTEMPT", "2"),
    ("DISPATCHER_SHA", "f" * 40),
])
def test_writer_cli_snapshots_and_writes_only_same_attempt_bundle(
    prepared, tmp_path, monkeypatch, capsys, identity_field, identity_value,
):
    root, gh, artifact = prepared
    for key, value in {
        "GITHUB_REPOSITORY": gh.repository, "GH_TOKEN": "fake", "GITHUB_SHA": gh.main,
        "GITHUB_RUN_ID": "42", "GITHUB_RUN_ATTEMPT": "1", "DISPATCHER_SHA": "d" * 40,
        "RELEASE_MODE": "prepare", "PROPOSAL_PR": "", "EXPECTED_HEAD": "", "MERGED_SHA": "",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.setattr(r, "GitHub", lambda repository, token: gh)
    output = tmp_path / "request.json"
    assert r.main(["snapshot", "--output", str(output)]) == 0
    assert r.load_json(output.read_bytes()) == artifact["request"]
    path = tmp_path / "bundle/proposal.json"
    path.parent.mkdir()
    path.write_bytes(r.canonical(artifact))
    assert r.main(["write", "--artifact", str(path)]) == 0
    assert gh.prs[1]["draft"] is True
    assert "Proposal result 1." in capsys.readouterr().out
    writes = copy.deepcopy(gh.writes)
    monkeypatch.setenv(identity_field, identity_value)
    assert r.main(["write", "--artifact", str(path)]) == 1
    assert "Artifact snapshot is stale or mismatched" in capsys.readouterr().err
    assert gh.writes == writes


def test_real_gh_command_is_explicit_draft_verify_tag_and_sha(tmp_path, monkeypatch):
    executable = tmp_path / "gh"
    executable.write_text(
        "#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\n"
        f"Path({str(tmp_path / 'args.json')!r}).write_text(json.dumps(sys.argv[1:]))\n"
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + str(Path(sys.executable).parent) + ":" + os.environ["PATH"])
    gh = r.GitHub("nilpath/test", "fake")
    gh.release_create("alpha/v1.2.4", "alpha 1.2.4", "Reviewed notes", "e" * 40)
    args = json.loads((tmp_path / "args.json").read_text())
    assert args[:10] == ["release", "create", "alpha/v1.2.4", "--repo", "nilpath/test",
                         "--draft", "--verify-tag", "--target", "e" * 40, "--title"]
    assert "--clobber" not in args


def test_actual_snapshot_and_write_cli_route_without_candidate_dependencies(tmp_path):
    input_sha = "a" * 40
    raw = b"# Empty\n"
    sha = blob_sha(raw)
    routes = {
        "/repos/nilpath/test/git/ref/heads/main": {
            "ref": "refs/heads/main", "object": {"type": "commit", "sha": input_sha},
        },
        "/repos/nilpath/test/pulls?state=open&base=main&per_page=100&page=1": [],
        f"/repos/nilpath/test/git/trees/{input_sha}?recursive=1": {
            "truncated": False, "tree": [
                {"path": ".release/decisions.toml", "mode": "100644", "type": "blob", "sha": sha},
            ],
        },
        f"/repos/nilpath/test/git/blobs/{sha}": {
            "encoding": "base64", "size": len(raw), "content": base64.b64encode(raw).decode(),
        },
        "/repos/nilpath/test/commits?" + urlencode({"sha": input_sha, "path": ".release/plan.json"})
        + "&per_page=100&page=1": [],
    }
    driver = """
import io, json, runpy, sys, urllib.request
routes = json.loads(sys.argv.pop(1))
class Response(io.BytesIO):
    status = 200
class Opener:
    def open(self, request, timeout):
        assert request.host == "api.github.com" and request.method == "GET"
        return Response(json.dumps(routes[request.selector]).encode())
urllib.request.build_opener = lambda *handlers: Opener()
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
    env = {
        "GITHUB_REPOSITORY": "nilpath/test", "GH_TOKEN": "fake", "GITHUB_SHA": input_sha,
        "GITHUB_RUN_ID": "42", "GITHUB_RUN_ATTEMPT": "1", "DISPATCHER_SHA": "d" * 40,
        "RELEASE_MODE": "prepare", "GITHUB_OUTPUT": str(tmp_path / "github-output"),
    }
    cli = [sys.executable, "-S", "-c", driver, json.dumps(routes), str(ROOT / "tools/release.py")]
    output = tmp_path / "request.json"
    result = subprocess.run([*cli, "snapshot", "--output", str(output)],
                            cwd=tmp_path, env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert json.loads(output.read_bytes()) == request(input_sha)
    assert (tmp_path / "github-output").read_text() == f"kind=proposal\ninput_sha={input_sha}\n"
    artifact = {"request": request(input_sha), "plan": None, "files": []}
    artifact["digest"] = r.digest(r.canonical(artifact))
    path = tmp_path / "bundle/proposal.json"
    path.parent.mkdir()
    path.write_bytes(r.canonical(artifact))
    result = subprocess.run([*cli, "write", "--artifact", str(path)],
                            cwd=tmp_path, env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "No component release changes.\nProposal result None.\n"
    artifact["request"]["repository"] = "other/repo"
    artifact["digest"] = r.digest(r.canonical({k: v for k, v in artifact.items() if k != "digest"}))
    path.write_bytes(r.canonical(artifact))
    result = subprocess.run([*cli, "write", "--artifact", str(path)],
                            cwd=tmp_path, env=env, text=True, capture_output=True)
    assert result.returncode == 1
    assert result.stderr == "release: Artifact snapshot is stale or mismatched\n"
    assert result.stdout == ""


@pytest.mark.parametrize("edited", [False, True])
@pytest.mark.parametrize("upgrade", ["cliff", "updater"])
@pytest.mark.parametrize("blocked", [False, True])
def test_active_historical_proposals_refresh_after_current_tool_or_updater_changes(repo, monkeypatch, edited, upgrade, blocked):
    sha = change(repo, "unknown wording" if blocked else "fix(alpha): repair")
    gh = FakeGitHub(repo)
    r.prepare(repo, r.propose(repo).plan)
    r.create_proposal(gh, r.bundle(repo, request(gh.main)))
    decision = r.Decision("alpha", sha, "none", "Reviewed exclusion.")
    if edited:
        edit_proposal_decisions(gh, (decision,))
    advance_main(repo, gh)
    source = repo / "tools/release.py"
    if upgrade == "cliff":
        source.write_text(source.read_text().replace('CLIFF_VERSION = "2.13.1"', 'CLIFF_VERSION = "2.14.0"'))
        monkeypatch.setattr(r, "CLIFF_VERSION", "2.14.0")
    else:
        source.write_text(source.read_text().replace(
            "return schema1_changelog_update(raw, plan)", 'return b"Changed current updater\\n"'))
        monkeypatch.setattr(r, "changelog_update", lambda raw, plan: b"Changed current updater\n")
    gh.main = commit(repo, "ci: change current release generation")
    gh.load_commit(gh.main)
    writes = copy.deepcopy(gh.writes)
    req = r.snapshot(gh, mode="prepare", proposal_pr=1 if edited else None,
                     expected_head="b" * 40 if edited else None, merged_sha=None,
                     event_sha=gh.main, identity=IDENTITY)
    assert req["decisions"] == ([decision.__dict__] if edited else [])
    assert req["input_sha"] == gh.main and req["proposal_pr"] == 1
    assert gh.writes == writes


@pytest.mark.parametrize("upgrade", ["cliff", "updater"])
def test_first_draft_uses_historical_bytes_after_current_generation_changes(prepared, monkeypatch, upgrade):
    gh, plan, merged, head = reviewed_fixture(prepared)
    if upgrade == "cliff":
        monkeypatch.setattr(r, "CLIFF_VERSION", "2.14.0")
    else:
        monkeypatch.setattr(r, "changelog_update", lambda raw, plan: b"Changed current updater\n")
    monkeypatch.setattr(r, "expected_updates", lambda *args: pytest.fail("First draft must use the historical contract"))
    reviewed = r.reviewed_release(gh, 1, merged, plan)
    assert reviewed.head_sha == head
    r.reconcile_drafts(gh, reviewed)
    assert gh.tags == {"alpha/v1.2.4": {"type": "commit", "sha": merged}}
    assert gh.releases[0]["body"] == plan["releases"][0]["notes"].rstrip() + "\n\n" + r.release_marker(
        plan["releases"][0], merged, plan["plan_id"]) + "\n"


@pytest.mark.parametrize("path", [
    ".github/workflows/ci.yml", ".github/workflows/release.yml", "tools/release.py",
    "tools/pr_conventions.sh", "cliff.toml", "README.md", "CHANGELOG.md",
])
@pytest.mark.parametrize("merged", [False, True])
def test_historical_validation_never_trusts_changed_payload_or_pr_owned_verifiers(prepared, monkeypatch, path, merged):
    if merged:
        gh, plan, merge_sha, head = reviewed_fixture(prepared)
    else:
        _, gh, artifact = prepared
        r.create_proposal(gh, artifact)
        head = gh.prs[1]["head"]["sha"]
    monkeypatch.setattr(r, "CLIFF_VERSION", "2.14.0")
    monkeypatch.setattr(r, "changelog_update", lambda raw, plan: b"Changed current updater\n")
    tree = gh.trees[head]
    raw = gh.blobs[tree[path]["sha"]] + b"\nUnapproved edit\n"
    sha = blob_sha(raw)
    gh.blobs[sha] = raw
    tree[path]["sha"] = sha
    writes = copy.deepcopy(gh.writes)
    with pytest.raises(r.ReleaseError):
        if merged:
            r.reviewed_release(gh, 1, merge_sha, plan)
        else:
            snapshot_prepare(gh)
    assert gh.writes == writes


@pytest.mark.parametrize("merged", [False, True])
def test_historical_validation_checks_payload_file_modes(prepared, monkeypatch, merged):
    if merged:
        gh, plan, merge_sha, head = reviewed_fixture(prepared)
    else:
        _, gh, _ = prepared
        r.create_proposal(gh, prepared[2])
        head = gh.prs[1]["head"]["sha"]
    monkeypatch.setattr(r, "CLIFF_VERSION", "2.14.0")
    gh.trees[head]["README.md"]["mode"] = "100755"
    writes = copy.deepcopy(gh.writes)
    with pytest.raises(r.ReleaseError):
        if merged:
            r.reviewed_release(gh, 1, merge_sha, plan)
        else:
            snapshot_prepare(gh)
    assert gh.writes == writes


@pytest.fixture
def decision_merge(repo):
    sha = change(repo, "unknown wording")
    decision = r.Decision("alpha", sha, "none", "Reviewed exclusion.")
    gh = FakeGitHub(repo)
    r.prepare(repo, r.propose(repo).plan)
    r.create_proposal(gh, r.bundle(repo, request(gh.main)))
    edit_proposal_decisions(gh, (decision,))
    r.prepare(repo, r.propose(repo, (decision,)).plan)
    req = request(gh.main, decisions=[decision.__dict__], proposal_pr=1, expected_head="b" * 40)
    return reviewed_fixture((repo, gh, r.bundle(repo, req)), 2)


@pytest.mark.parametrize("bad", ["review", "ci"])
def test_unvalidated_decision_only_merge_cannot_be_accepted_as_history(decision_merge, bad):
    gh, plan, merged, _ = decision_merge
    if bad == "review":
        gh.routes["pulls/2/reviews?per_page=100&page=1"] = []
    else:
        gh.routes["actions/runs/70/attempts/2/jobs?per_page=100&page=1"]["jobs"][1]["conclusion"] = "failure"
    writes = copy.deepcopy(gh.writes)
    with pytest.raises(r.ReleaseError, match="No human approval|Missing successful exact-head"):
        r.reviewed_release(gh, 2, merged, plan)
    set_prior_history(gh, merged, merged)
    with pytest.raises(r.ReleaseError, match="Incomplete prior decision transaction"):
        r.prior_complete(gh, merged)
    assert gh.writes == writes and gh.tags == {} and gh.releases == []


def test_decision_only_receipt_is_durable_and_identity_bound(decision_merge, monkeypatch):
    gh, plan, merged, head = decision_merge
    reviewed = r.reviewed_release(gh, 2, merged, plan)
    set_prior_history(gh, merged, merged)
    with pytest.raises(r.ReleaseError, match="Incomplete prior decision transaction"):
        r.prior_complete(gh, merged)
    r.reconcile_drafts(gh, reviewed)
    assert gh.comments[2] == [{
        "id": 200, "body": f"<!-- nilpath-release-complete:1:nilpath/test:2:{head}:{merged}:{plan['plan_id']} -->",
        "user": {"login": r.BOT, "id": r.BOT_ID},
    }]
    assert gh.tags == {} and gh.releases == []
    for path in list(gh.routes):
        if path.startswith("actions/") or "/check-runs" in path or "/reviews?" in path:
            gh.routes[path] = r.ReleaseError("CI record deleted")
    monkeypatch.setattr(r, "CLIFF_VERSION", "2.14.0")
    monkeypatch.setattr(r, "historical_updates", lambda *args: pytest.fail("Historical receipt must not regenerate"))
    writes = copy.deepcopy(gh.writes)
    assert r.reviewed_release(gh, 2, merged, plan).head_sha == head
    r.prior_complete(gh, merged)
    r.reconcile_drafts(gh, reviewed)
    assert gh.writes == writes


@pytest.mark.parametrize("bad", ["repository", "pr", "head", "merge", "plan", "schema", "duplicate", "id"])
def test_conflicting_decision_completion_receipts_are_not_adopted(decision_merge, bad):
    gh, plan, merged, head = decision_merge
    reviewed = r.reviewed_release(gh, 2, merged, plan)
    r.reconcile_drafts(gh, reviewed)
    comment = gh.comments[2][0]
    if bad == "duplicate":
        gh.comments[2].append({**copy.deepcopy(comment), "id": 201})
    elif bad == "id":
        comment["id"] = None
    else:
        old, new = {
            "repository": ("nilpath/test", "other/repo"), "pr": (":2:", ":9:"),
            "head": (head, "a" * 40), "merge": (merged, "a" * 40),
            "plan": (plan["plan_id"], "f" * 64), "schema": ("complete:1:", "complete:2:"),
        }[bad]
        comment["body"] = comment["body"].replace(old, new, 1)
    writes = copy.deepcopy(gh.writes)
    with pytest.raises(r.ReleaseError, match="decision completion receipt|Repeated pagination item"):
        r.reviewed_release(gh, 2, merged, plan)
    set_prior_history(gh, merged, merged)
    with pytest.raises(r.ReleaseError, match="decision completion receipt|Repeated pagination item"):
        r.prior_complete(gh, merged)
    assert gh.writes == writes


@pytest.mark.parametrize("already_completed", [False, True])
def test_untrusted_completion_markers_do_not_block_or_complete_transactions(decision_merge, already_completed):
    gh, plan, merged, _ = decision_merge
    reviewed = r.reviewed_release(gh, 2, merged, plan)
    if already_completed:
        r.reconcile_drafts(gh, reviewed)
        gh.routes["actions/workflows/ci.yml"] = r.ReleaseError("CI record deleted")
    gh.comments.setdefault(2, []).append({
        "id": 999,
        "body": "Quoted completion marker: " + r.completion_marker(gh, reviewed),
        "user": {"login": "unrelated-contributor", "id": 999},
    })
    writes = copy.deepcopy(gh.writes)
    r.reconcile_drafts(gh, r.reviewed_release(gh, 2, merged, plan))
    receipts = [comment for comment in gh.comments[2] if comment["user"]["id"] == r.BOT_ID]
    assert len(receipts) == 1
    assert receipts[0]["body"] == r.completion_marker(gh, reviewed)
    assert len(gh.writes) == len(writes) + (0 if already_completed else 1)


@pytest.mark.parametrize("user", [
    {"login": "maintainer", "id": r.BOT_ID},
    {"login": r.BOT, "id": 1},
    None,
])
def test_forged_completion_receipts_do_not_replace_first_completion_checks(decision_merge, user):
    gh, plan, merged, _ = decision_merge
    reviewed = r.reviewed_release(gh, 2, merged, plan)
    gh.comments[2] = [{"id": 200, "body": r.completion_marker(gh, reviewed), "user": user}]
    gh.routes["actions/workflows/ci.yml"] = r.ReleaseError("CI record deleted")
    writes = copy.deepcopy(gh.writes)
    with pytest.raises(r.ReleaseError, match="CI record deleted"):
        r.reviewed_release(gh, 2, merged, plan)
    set_prior_history(gh, merged, merged)
    with pytest.raises(r.ReleaseError, match="Incomplete prior decision transaction"):
        r.prior_complete(gh, merged)
    assert gh.writes == writes


@pytest.mark.parametrize("interruption", ["before-write", "after-write", "before-confirmation"])
def test_decision_receipt_interruption_retries_converge_without_duplicate_writes(decision_merge, monkeypatch, interruption):
    gh, plan, merged, _ = decision_merge
    reviewed = r.reviewed_release(gh, 2, merged, plan)
    post = gh.post
    path = "issues/2/comments"
    if interruption == "before-write":
        gh.fail = path
    else:
        def interrupted_post(suffix, body):
            result = post(suffix, body)
            if suffix == path:
                if interruption == "after-write":
                    raise r.ReleaseError("Injected remote failure after receipt persistence")
                gh.routes[path + "?per_page=100&page=1"] = r.ReleaseError("Injected confirmation failure")
            return result
        monkeypatch.setattr(gh, "post", interrupted_post)
    with pytest.raises(r.ReleaseError, match="Injected"):
        r.reconcile_drafts(gh, reviewed)
    monkeypatch.setattr(gh, "post", post)
    gh.routes.pop(path + "?per_page=100&page=1", None)
    if interruption != "before-write":
        gh.routes["pulls/2/reviews?per_page=100&page=1"] = r.ReleaseError("CI record deleted")
    r.reconcile_drafts(gh, r.reviewed_release(gh, 2, merged, plan))
    assert len(gh.comments[2]) == 1
    assert gh.comments[2][0]["body"] == r.completion_marker(gh, reviewed)
    assert gh.tags == {} and gh.releases == []


@pytest.mark.parametrize("owner", ["human", "fork", "deleted-fork", "wrong-bot-id", "wrong-bot-login"])
@pytest.mark.parametrize("lookalike", ["branch", "marker"])
def test_discovery_ignores_foreign_open_and_merged_lookalikes(prepared, owner, lookalike):
    _, gh, artifact = prepared
    pr = {
        "id": 7, "number": 7, "user": {"login": r.BOT, "id": r.BOT_ID},
        "head": {"ref": "release/proposal-spam" if lookalike == "branch" else "ordinary-branch",
                 "sha": "f" * 40, "repo": {"full_name": gh.repository}},
        "base": {"ref": "main", "repo": {"full_name": gh.repository}},
        "body": r.PROPOSAL_MARKER + "f" * 64 + " -->" if lookalike == "marker" else "",
        "state": "open", "draft": False, "merged": False,
    }
    if owner in {"human", "wrong-bot-login"}:
        pr["user"]["login"] = "maintainer"
    if owner in {"human", "wrong-bot-id"}:
        pr["user"]["id"] = 1
    if owner == "fork":
        pr["head"]["repo"]["full_name"] = "attacker/fork"
    elif owner == "deleted-fork":
        pr["head"]["repo"] = None
    gh.prs[7] = pr
    assert snapshot_prepare(gh)["proposal_pr"] is None
    gh.routes[f"commits/{gh.main}/pulls?per_page=100&page=1"] = [{**copy.deepcopy(pr), "state": "closed", "merged": True}]
    req = r.snapshot(gh, mode="auto", proposal_pr=None, expected_head=None, merged_sha=None,
                     event_sha=gh.main, identity=IDENTITY)
    assert req["kind"] == "proposal" and req["input_sha"] == gh.main
    with pytest.raises(r.ReleaseError):
        r.snapshot(gh, mode="prepare", proposal_pr=7, expected_head="f" * 40, merged_sha=None,
                   event_sha=gh.main, identity=IDENTITY)
    assert gh.writes == []
    assert r.create_proposal(gh, artifact) == 2


@pytest.mark.parametrize("bad", ["marker", "branch", "base"])
def test_genuine_bot_proposal_discovery_still_fails_closed(prepared, bad):
    _, gh, artifact = prepared
    r.create_proposal(gh, artifact)
    if bad == "marker":
        gh.prs[1]["body"] = "Missing marker"
    elif bad == "branch":
        gh.prs[1]["head"]["ref"] = "ordinary-branch"
    else:
        gh.prs[1]["base"]["ref"] = "other"
    writes = copy.deepcopy(gh.writes)
    with pytest.raises(r.ReleaseError):
        snapshot_prepare(gh)
    gh.routes[f"commits/{gh.main}/pulls?per_page=100&page=1"] = [gh.prs[1]]
    with pytest.raises(r.ReleaseError):
        r.snapshot(gh, mode="auto", proposal_pr=None, expected_head=None, merged_sha=None,
                   event_sha=gh.main, identity=IDENTITY)
    assert gh.writes == writes

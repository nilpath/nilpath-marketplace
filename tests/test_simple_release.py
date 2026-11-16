import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import open_release as opening
import prepare_release as preparing
import tag_release as tagging
from buildkit.build import build


def command(root, *args):
    return subprocess.check_output(args, cwd=root, text=True).strip()


def commit(root, message):
    command(root, "git", "add", "--all")
    command(root, "git", "commit", "-qm", message)
    return command(root, "git", "rev-parse", "HEAD")


def write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    command(root, "git", "init", "-q", "-b", "main")
    command(root, "git", "config", "user.name", "Tester")
    command(root, "git", "config", "user.email", "test@example.com")
    shutil.copytree(ROOT / "src/harnesses", root / "src/harnesses")
    shutil.copy(ROOT / "src/marketplace.yaml", root / "src/marketplace.yaml")
    marketplace = root / "src/marketplace.yaml"
    marketplace.write_text(marketplace.read_text() + "  description: Test fixture.\n")
    shutil.copy(ROOT / "cliff.toml", root / "cliff.toml")
    shutil.copy(ROOT / ".gitignore", root / ".gitignore")
    for path in ("open_release.py", "prepare_release.py", "tag_release.py"):
        write(root, f"tools/{path}", (ROOT / "tools" / path).read_text())
    for plugin, version in (("alpha", "1.2.3"), ("beta", "0.4.8")):
        write(root, f"src/plugins/{plugin}/plugin.yaml", f"name: {plugin}\nversion: {version}\n")
        write(root, f"src/plugins/{plugin}/README.md", f"# {plugin}\n\nVersion: **{version}**\n\nHistorical 0.0.1.\n")
        write(root, f"src/plugins/{plugin}/skills/one/SKILL.md.j2",
              "---\nname: one\ndescription: A test skill.\ntargets: [claude, copilot, codex]\n---\n\nOriginal content.\n")
    write(root, "README.md", "| **alpha** | 1.2.3 | A |\n| **beta** | 0.4.8 | B |\nHistory 0.0.1.\n")
    write(root, "CHANGELOG.md", "# Historical notes\n\n## [Unreleased]\n\nKeep these exact bytes.\n")
    initial = commit(root, "feat: initialize")
    write(root, ".release/baselines.toml", f'[baseline]\nalpha = "{initial}"\nbeta = "{initial}"\n')
    build(root)
    commit(root, "ci: install release tools")
    remote = tmp_path / "origin.git"
    command(tmp_path, "git", "init", "--bare", "-q", str(remote))
    command(root, "git", "remote", "add", "origin", str(remote))
    command(root, "git", "push", "-q", "origin", "main")
    yield root
    for line in command(root, "git", "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree ") and line != f"worktree {root}":
            work = Path(line.removeprefix("worktree "))
            command(root, "git", "worktree", "remove", str(work))
            work.parent.rmdir()


def request(root):
    base = command(root, "git", "rev-parse", "HEAD")
    command(root, "git", "push", "-q", "origin", "HEAD:main")
    command(root, "git", "checkout", "-qb", "release/alpha-v1.2.4")
    write(root, "src/plugins/alpha/plugin.yaml", "name: alpha\nversion: 1.2.4\n")
    head = commit(root, "chore(alpha): release v1.2.4")
    command(root, "git", "push", "-q", "origin", "HEAD:refs/heads/release/alpha-v1.2.4")
    return base, head


class GitHub:
    def __init__(self, root, base, head):
        self.root = root
        self.main = base
        self.pr = {
            "state": "open", "merged": False, "merge_commit_sha": None,
            "base": {"sha": base, "ref": "main", "repo": {"full_name": "nilpath/test"}},
            "head": {"sha": head, "ref": "release/alpha-v1.2.4", "repo": {"full_name": "nilpath/test"}},
        }
        self.tags = {}
        self.releases = {}
        self.writes = []
        self.fail_release = False

    def api(self, root, repo, path, *, missing=False, **fields):
        assert repo == "nilpath/test"
        if fields:
            self.writes.append((path, fields))
        if path == "pulls/7":
            return self.pr
        if path == "git/ref/heads/main":
            return {"object": {"sha": self.main}}
        if path.startswith("git/ref/tags/"):
            return self.tags.get("alpha/v1.2.4")
        if path == "git/refs":
            self.tags[fields["ref"].removeprefix("refs/tags/")] = {
                "object": {"type": "commit", "sha": fields["sha"]},
            }
            return self.tags["alpha/v1.2.4"]
        if path.startswith("releases/tags/"):
            release = self.releases.get("alpha/v1.2.4")
            return release if release is not None and not release["draft"] else None
        if path.startswith("releases?per_page=100&page="):
            offset = (int(path.rpartition("=")[2]) - 1) * 100
            return list(self.releases.values())[offset:offset + 100]
        if path == "releases":
            if self.fail_release:
                raise opening.ReleaseError("Draft creation failed")
            self.releases[fields["tag_name"]] = {**fields, "html_url": "https://example.test/draft"}
            return self.releases[fields["tag_name"]]
        raise AssertionError((path, fields))


def connect(monkeypatch, root, base, head):
    gh = GitHub(root, base, head)
    for module in (preparing, tagging):
        monkeypatch.setattr(module, "repository", lambda root: "nilpath/test")
        monkeypatch.setattr(module, "gh_api", gh.api)
    return gh


def prepared(monkeypatch, root):
    base, head = request(root)
    gh = connect(monkeypatch, root, base, head)
    preparing.prepare_release(base, head, root=root, pr_number=7)
    gh.pr["head"]["sha"] = command(root, "git", "ls-remote", "origin", gh.pr["head"]["ref"]).split()[0]
    return base, gh.pr["head"]["sha"], gh


@pytest.mark.parametrize("version,bump,expected", [
    ("0.0.7", "major", "1.0.0"), ("0.0.7", "minor", "0.1.0"),
    ("0.0.7", "patch", "0.0.8"), ("1.9.9", "major", "2.0.0"),
    ("1.9.9", "minor", "1.10.0"), ("1.9.9", "patch", "1.9.10"),
])
def test_semantic_bumps(version, bump, expected):
    assert opening.bump_version(version, bump) == expected


@pytest.mark.parametrize("version,bump", [
    ("01.2.3", "patch"), ("1.2.3-rc1", "patch"), ("1.2", "patch"), ("1.2.3", "auto"),
])
def test_invalid_bumps(version, bump):
    with pytest.raises(opening.ReleaseError):
        opening.bump_version(version, bump)


def fake_open_gh(monkeypatch, fail=False):
    original = opening.run
    calls = []

    def run(root, *args, **kwargs):
        if args[:2] == ("gh", "pr"):
            calls.append(args)
            if fail:
                raise opening.ReleaseError("GitHub unavailable")
            return b"https://example.test/pr/7\n"
        return original(root, *args, **kwargs)

    monkeypatch.setattr(opening, "repository", lambda root: "nilpath/test")
    monkeypatch.setattr(opening, "run", run)
    return calls


def test_open_isolated_worktree_and_scalar_only_commit(repo, monkeypatch):
    calls = fake_open_gh(monkeypatch)
    write(repo, "staged.txt", "keep staged\n")
    command(repo, "git", "add", "staged.txt")
    write(repo, "src/plugins/alpha/plugin.yaml", "Uncommitted local version work\n")
    write(repo, "untracked.txt", "keep untracked\n")
    before = command(repo, "git", "status", "--porcelain")
    index = (repo / ".git/index").read_bytes()
    head = command(repo, "git", "rev-parse", "HEAD")
    assert opening.open_release("alpha", "patch", repo) == "https://example.test/pr/7"
    assert command(repo, "git", "status", "--porcelain") == before
    assert (repo / ".git/index").read_bytes() == index
    assert command(repo, "git", "rev-parse", "HEAD") == head
    assert command(repo, "git", "branch", "--show-current") == "main"
    assert (repo / "src/plugins/alpha/plugin.yaml").read_text() == "Uncommitted local version work\n"
    branch = "release/alpha-v1.2.4"
    assert command(repo, "git", "diff", "--name-only", f"{head}..{branch}") == "src/plugins/alpha/plugin.yaml"
    assert command(repo, "git", "show", f"{branch}:src/plugins/alpha/plugin.yaml") == "name: alpha\nversion: 1.2.4"
    assert command(repo, "git", "show", "-s", "--format=%P", branch) == head
    assert calls[0][calls[0].index("--head") + 1] == branch
    assert "--draft" in calls[0]
    assert command(repo, "git", "worktree", "list", "--porcelain").count("worktree ") == 1
    with pytest.raises(opening.ReleaseError, match="already exists"):
        opening.open_release("alpha", "patch", repo)


def test_open_requires_deployed_main(repo, monkeypatch):
    fake_open_gh(monkeypatch)
    command(repo, "git", "rm", "tools/tag_release.py")
    commit(repo, "chore: older deployment")
    command(repo, "git", "push", "-q", "origin", "main")
    with pytest.raises(opening.ReleaseError, match="does not support"):
        opening.open_release("alpha", "patch", repo)
    assert command(repo, "git", "branch", "--list", "release/*") == ""


def test_open_does_not_replace_existing_remote_branch(repo, monkeypatch):
    calls = fake_open_gh(monkeypatch)
    original = command(repo, "git", "rev-parse", "HEAD")
    command(repo, "git", "push", "-q", "origin", "HEAD:refs/heads/release/alpha-v1.2.4")
    with pytest.raises(opening.ReleaseError, match="Remote branch.*already exists"):
        opening.open_release("alpha", "patch", repo)
    assert command(repo, "git", "ls-remote", "origin", "release/alpha-v1.2.4").split()[0] == original
    assert calls == []
    assert command(repo, "git", "branch", "--list", "release/*") == ""


def test_open_reports_and_retains_partial_failure(repo, monkeypatch):
    fake_open_gh(monkeypatch, fail=True)
    with pytest.raises(opening.ReleaseError, match="Retained worktree") as error:
        opening.open_release("alpha", "patch", repo)
    assert "gh pr list" in str(error.value)
    assert "gh pr create" in str(error.value)
    assert "-c core.hooksPath=/dev/null push origin --force-with-lease=refs/heads/release/alpha-v1.2.4:" in str(error.value)
    assert command(repo, "git", "ls-remote", "--heads", "origin", "release/alpha-v1.2.4").endswith("refs/heads/release/alpha-v1.2.4")
    assert command(repo, "git", "branch", "--show-current") == "main"
    assert command(repo, "git", "worktree", "list", "--porcelain").count("worktree ") == 2


def test_open_rejects_branch_created_after_absence_check(repo, monkeypatch):
    calls = fake_open_gh(monkeypatch)
    original = opening.git
    base = command(repo, "git", "rev-parse", "HEAD")
    ref = "refs/heads/release/alpha-v1.2.4"

    def concurrent_creation(root, *args):
        if "push" in args and args[-1] == f"HEAD:{ref}":
            command(repo, "git", "--git-dir", str(repo.parent / "origin.git"),
                    "update-ref", ref, base, "0" * 40)
        return original(root, *args)

    monkeypatch.setattr(opening, "git", concurrent_creation)
    with pytest.raises(opening.ReleaseError, match="Retained worktree"):
        opening.open_release("alpha", "patch", repo)
    assert command(repo, "git", "ls-remote", "origin", ref).split()[0] == base
    assert calls == []


def test_existing_target_tag_blocks_open_and_preparation(repo, monkeypatch):
    calls = fake_open_gh(monkeypatch)
    command(repo, "git", "tag", "alpha/v1.2.3")
    command(repo, "git", "tag", "alpha/v1.2.4")
    command(repo, "git", "push", "-q", "origin", "refs/tags/alpha/v1.2.4")
    command(repo, "git", "tag", "-d", "alpha/v1.2.4")
    with pytest.raises(opening.ReleaseError, match="Tag alpha/v1.2.4 already exists"):
        opening.open_release("alpha", "patch", repo)
    assert calls == []
    command(repo, "git", "fetch", "-q", "--tags", "origin")
    base, head = request(repo)
    connect(monkeypatch, repo, base, head)
    with pytest.raises(opening.ReleaseError, match="Tag alpha/v1.2.4 already exists"):
        preparing.prepare_release(base, head, root=repo, pr_number=7)
    assert command(repo, "git", "ls-remote", "origin", "release/alpha-v1.2.4").split()[0] == head


def test_prepare_scopes_output_preserves_registry_and_history(repo, monkeypatch):
    write(repo, "src/plugins/beta/skills/one/SKILL.md.j2",
          "---\nname: one\ndescription: Changed beta.\ntargets: [claude]\n---\n\nUnreleased beta content.\n")
    write(repo, "dist/copilot/plugins/beta/executable", "installed beta\n")
    (repo / "dist/copilot/plugins/beta/executable").chmod(0o755)
    for registry in preparing.REGISTRIES:
        path = repo / registry
        data = json.loads(path.read_text())
        data["custom"] = {"marketplace": "keep"}
        next(e for e in data["plugins"] if e["name"] == "beta")["unknown"] = [9, 8, 7]
        path.write_text(json.dumps(data, indent=2) + "\n")
    commit(repo, "feat(beta): pending beta-only change")
    base, head, gh = prepared(monkeypatch, repo)
    before = command(repo, "git", "ls-tree", "-r", base, "--", "dist")
    after = command(repo, "git", "ls-tree", "-r", head, "--", "dist")
    assert [l for l in before.splitlines() if "/beta/" in l] == [l for l in after.splitlines() if "/beta/" in l]
    assert "100755" in next(l for l in after.splitlines() if "/beta/executable" in l)
    assert opening.blob(repo, head, "dist/claude/plugins/alpha/README.md") == b"# alpha\n\nVersion: **1.2.4**\n\nHistorical 0.0.1.\n"
    assert opening.blob(repo, head, "README.md") == b"| **alpha** | 1.2.4 | A |\n| **beta** | 0.4.8 | B |\nHistory 0.0.1.\n"
    for registry in preparing.REGISTRIES:
        old = opening.blob(repo, base, registry)
        new = opening.blob(repo, head, registry)
        a, b = json.loads(old), json.loads(new)
        assert a["custom"] == b["custom"] == {"marketplace": "keep"}
        assert [e for e in a["plugins"] if e["name"] == "beta"] == [e for e in b["plugins"] if e["name"] == "beta"]
        assert [e["name"] for e in b["plugins"]] == ["alpha", "beta"]
        assert new[new.index(b'"name": "beta"'):] == old[old.index(b'"name": "beta"'):]
    assert opening.blob(repo, head, "CHANGELOG.md") == (
        b"# Historical notes\n\n## alpha/v1.2.4\n\nNo shipped changes since the previous release.\n\n"
        b"## [Unreleased]\n\nKeep these exact bytes.\n"
    )
    assert preparing.prepare_release(base, head, True, root=repo).tag == "alpha/v1.2.4"
    before_retry = command(repo, "git", "ls-remote", "origin", gh.pr["head"]["ref"])
    preparing.prepare_release(base, head, root=repo, pr_number=7)
    assert command(repo, "git", "ls-remote", "origin", gh.pr["head"]["ref"]) == before_retry


def test_prepare_handles_selected_deletions_and_client_omission(repo, monkeypatch):
    write(repo, "src/plugins/alpha/skills/one/SKILL.md.j2",
          "---\nname: one\ndescription: Claude only.\ntargets: [claude]\n---\n\nNow Claude only.\n")
    write(repo, "dist/claude/plugins/alpha/obsolete.txt", "remove this\n")
    commit(repo, "refactor(alpha): support Claude only")
    base, head, _ = prepared(monkeypatch, repo)
    paths = command(repo, "git", "ls-tree", "-r", "--name-only", head).splitlines()
    assert "dist/claude/plugins/alpha/.claude-plugin/plugin.json" in paths
    assert not any(p.startswith(("dist/copilot/plugins/alpha/", "dist/codex/plugins/alpha/")) or p.endswith("/obsolete.txt") for p in paths)
    for registry in preparing.REGISTRIES[1:]:
        assert [e["name"] for e in json.loads(opening.blob(repo, head, registry))["plugins"]] == ["beta"]
    assert command(repo, "git", "ls-tree", "-r", head, "--", "dist/copilot/plugins/beta") == command(repo, "git", "ls-tree", "-r", base, "--", "dist/copilot/plugins/beta")


def test_registry_splice_preserves_unknown_fields_and_metadata_bytes():
    raw = b'{"plugins":[{"name":"beta","unknown":[3,2,1]}, {"name":"alpha","policy":{"custom":true,"authentication":"OLD"},"custom":9}], "metadata": {"version":"unchanged", "custom":7}}\n'
    rendered = b'{"metadata":{"version":"must not ship"},"plugins":[{"name":"alpha","policy":{"authentication":"NEW"},"version":"1.2.4"}]}'
    result = preparing.replace_registry_entry(raw, rendered, "alpha")
    assert result.startswith(b'{"plugins":[{"name":"beta","unknown":[3,2,1]}, ')
    assert result.endswith(b'], "metadata": {"version":"unchanged", "custom":7}}\n')
    assert json.loads(result)["plugins"] == [
        {"name": "beta", "unknown": [3, 2, 1]},
        {"name": "alpha", "policy": {"custom": True, "authentication": "NEW"}, "custom": 9, "version": "1.2.4"},
    ]


@pytest.mark.parametrize("names", [["alpha", "beta"], ["beta", "alpha"], ["beta", "alpha", "gamma"], ["alpha"]])
def test_registry_selected_entry_deletion(names):
    raw = json.dumps({"plugins": [{"name": name, "unknown": 7} for name in names], "metadata": "keep"}).encode()
    result = preparing.replace_registry_entry(raw, b'{"plugins":[]}', "alpha")
    assert json.loads(result) == {"plugins": [{"name": name, "unknown": 7} for name in names if name != "alpha"], "metadata": "keep"}
    assert result.endswith(b', "metadata": "keep"}')


@pytest.mark.parametrize("raw", [b'{"plugins":[],"metadata":7}', b'{"plugins":[{"name":"beta","unknown":9}],"metadata":7}'])
def test_registry_adds_newly_supported_client_without_reordering_others(raw):
    result = preparing.replace_registry_entry(raw, b'{"plugins":[{"name":"alpha","version":"1.2.4"}]}', "alpha")
    assert result.endswith(b'],"metadata":7}')
    assert json.loads(result)["plugins"][-1] == {"name": "alpha", "version": "1.2.4"}
    if b"beta" in raw:
        assert result.startswith(b'{"plugins":[{"name":"beta","unknown":9},')


@pytest.mark.parametrize("path,content", [
    ("src/plugins/alpha/plugin.yaml", "name: replaced\nversion: 1.2.4\n"),
    ("src/plugins/beta/plugin.yaml", "name: beta\nversion: 0.4.9\n"),
    ("tools/evil.py", "raise RuntimeError('must never execute')\n"),
    ("tools/buildkit/src/buildkit/build.py", "raise RuntimeError('must never execute')\n"),
    ("dist/claude/plugins/alpha/evil.py", "raise RuntimeError('must never execute')\n"),
    ("README.md", "unrelated README rewrite\n"),
    ("src/plugins/alpha/plugin.yaml", "name: alpha\nversion: 1.2.9\n"),
])
def test_rejects_invalid_candidate_requests(repo, monkeypatch, path, content):
    base, _ = request(repo)
    write(repo, path, content)
    head = commit(repo, "chore: invalid release input")
    gh = connect(monkeypatch, repo, base, head)
    remote_before = command(repo, "git", "ls-remote", "origin", gh.pr["head"]["ref"])
    with pytest.raises(opening.ReleaseError):
        preparing.prepare_release(base, head, root=repo, pr_number=7)
    assert command(repo, "git", "ls-remote", "origin", gh.pr["head"]["ref"]) == remote_before


def test_unprepared_request_fails_exact_check(repo):
    base, head = request(repo)
    with pytest.raises(opening.ReleaseError, match="not prepared yet"):
        preparing.prepare_release(base, head, True, root=repo)


@pytest.mark.parametrize("readme", [None, "# Missing plugin table\n"])
def test_missing_root_version_field_fails_before_pushing(repo, monkeypatch, readme):
    if readme is None:
        (repo / "README.md").unlink()
    else:
        write(repo, "README.md", readme)
    commit(repo, "docs: remove version row")
    base, head = request(repo)
    connect(monkeypatch, repo, base, head)
    with pytest.raises(opening.ReleaseError, match="README.md"):
        preparing.prepare_release(base, head, root=repo, pr_number=7)
    assert command(repo, "git", "ls-remote", "origin", "release/alpha-v1.2.4").split()[0] == head


@pytest.mark.parametrize("path", ["src/plugins/alpha/plugin.yaml", "dist/claude/plugins/alpha/README.md"])
def test_rejects_candidate_mode_changes(repo, monkeypatch, path):
    base, _ = request(repo)
    (repo / path).chmod(0o755)
    head = commit(repo, "chore: unexpected executable mode")
    connect(monkeypatch, repo, base, head)
    with pytest.raises(opening.ReleaseError, match="neither"):
        preparing.prepare_release(base, head, root=repo, pr_number=7)
    assert command(repo, "git", "show", f"{head}:src/plugins/alpha/plugin.yaml") == "name: alpha\nversion: 1.2.4"


def test_exact_check_cli_and_branch_boundary(repo, monkeypatch):
    base, head, _ = prepared(monkeypatch, repo)
    args = [sys.executable, str(repo / "tools/prepare_release.py"),
            "--base-sha", base, "--head-sha", head, "--check"]
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "tools/buildkit/src")}
    valid = subprocess.run([*args, "--head-ref", "release/alpha-v1.2.4"], env=environment,
                           cwd=repo, capture_output=True, text=True)
    assert valid.returncode == 0, valid.stderr
    assert valid.stdout == "Validated alpha/v1.2.4\n"
    invalid = subprocess.run([*args, "--head-ref", "release/wrong"], env=environment,
                             cwd=repo, capture_output=True, text=True)
    assert invalid.returncode == 1
    assert invalid.stderr == "Invalid release branch\n"
    assert command(repo, "git", "status", "--porcelain") == ""


@pytest.mark.parametrize("stale", ["base", "head", "main"])
def test_stale_writes_fail_without_pushing(repo, monkeypatch, stale):
    base, head = request(repo)
    gh = connect(monkeypatch, repo, base, head)
    if stale == "main":
        gh.main = "a" * 40
    else:
        gh.pr[stale]["sha"] = "a" * 40
    with pytest.raises(opening.ReleaseError, match="changed|advanced|fetch.*failed"):
        preparing.prepare_release(base, head, root=repo, pr_number=7)
    assert command(repo, "git", "ls-remote", "origin", gh.pr["head"]["ref"]).split()[0] == head


def test_preparation_retry_after_push_succeeded_but_response_failed(repo, monkeypatch):
    base, head = request(repo)
    gh = connect(monkeypatch, repo, base, head)
    original = preparing.git
    pushes = []

    def lost_response(root, *args):
        result = original(root, *args)
        if args[:2] == ("push", "origin"):
            pushes.append(args)
            gh.pr["head"]["sha"] = args[-1].split(":")[0]
            raise opening.ReleaseError("Lost successful push response")
        return result

    monkeypatch.setattr(preparing, "git", lost_response)
    with pytest.raises(opening.ReleaseError, match="Re-run jobs"):
        preparing.prepare_release(base, head, root=repo, pr_number=7)
    assert gh.pr["head"]["sha"] != head
    assert preparing.prepare_release(base, head, root=repo, pr_number=7).tag == "alpha/v1.2.4"
    assert len(pushes) == 1
    assert command(repo, "git", "ls-remote", "origin", gh.pr["head"]["ref"]).split()[0] == gh.pr["head"]["sha"]


def test_head_change_during_render_is_rejected(repo, monkeypatch):
    base, head = request(repo)
    gh = connect(monkeypatch, repo, base, head)
    render = preparing.render_release

    def racing_render(*args):
        render(*args)
        gh.pr["head"]["sha"] = "b" * 40

    monkeypatch.setattr(preparing, "render_release", racing_render)
    with pytest.raises(opening.ReleaseError, match="changed"):
        preparing.prepare_release(base, head, root=repo, pr_number=7)
    assert command(repo, "git", "ls-remote", "origin", gh.pr["head"]["ref"]).split()[0] == head


def test_remote_head_change_after_final_check_is_rejected(repo, monkeypatch):
    base, head = request(repo)
    gh = connect(monkeypatch, repo, base, head)
    original = preparing.git
    ref = f"refs/heads/{gh.pr['head']['ref']}"

    def concurrent_rewind(root, *args):
        if args[:2] == ("push", "origin"):
            command(repo, "git", "--git-dir", str(repo.parent / "origin.git"),
                    "update-ref", ref, base, head)
        return original(root, *args)

    monkeypatch.setattr(preparing, "git", concurrent_rewind)
    with pytest.raises(opening.ReleaseError, match="No branch was overwritten"):
        preparing.prepare_release(base, head, root=repo, pr_number=7)
    assert command(repo, "git", "ls-remote", "origin", ref).split()[0] == base


def test_notes_include_plugin_and_shared_changes_not_other_plugin(repo, monkeypatch):
    for path, body, message in (
        ("src/plugins/alpha/README.md", "# alpha\n\nVersion: **1.2.3**\n\nAlpha feature.\n", "feat(alpha): alpha feature"),
        ("src/plugins/beta/README.md", "# beta\n\nBeta feature.\n", "feat(beta): beta feature"),
        ("src/harnesses/shared-note.txt", "A shared change\n", "fix: shared rendering"),
    ):
        write(repo, path, body)
        commit(repo, message)
    _, head, _ = prepared(monkeypatch, repo)
    notes = opening.blob(repo, head, "CHANGELOG.md").decode().split("## [Unreleased]")[0]
    assert "Alpha feature" in notes
    assert "Shared rendering" in notes
    assert "Beta feature" not in notes


@pytest.mark.parametrize("history", ["missing", "inconsistent", "previous-tag"])
def test_release_anchor_history(repo, monkeypatch, history):
    if history == "missing":
        (repo / ".release/baselines.toml").unlink()
        commit(repo, "chore: missing baseline")
    elif history == "inconsistent":
        command(repo, "git", "tag", "alpha/v1.1.0")
    else:
        command(repo, "git", "tag", "alpha/v1.2.3")
        write(repo, ".release/baselines.toml", '[baseline]\nalpha = "invalid"\n')
        commit(repo, "chore: prefer previous tag")
    base, head = request(repo)
    connect(monkeypatch, repo, base, head)
    if history == "previous-tag":
        preparing.prepare_release(base, head, root=repo, pr_number=7)
        new = command(repo, "git", "ls-remote", "origin", "release/alpha-v1.2.4").split()[0]
        assert opening.blob(repo, new, "CHANGELOG.md").startswith(b"# Historical notes\n\n## alpha/v1.2.4\n")
    else:
        with pytest.raises(opening.ReleaseError):
            preparing.prepare_release(base, head, root=repo, pr_number=7)
        assert command(repo, "git", "ls-remote", "origin", "release/alpha-v1.2.4").split()[0] == head


def merged_release(repo, monkeypatch):
    base, head, gh = prepared(monkeypatch, repo)
    command(repo, "git", "checkout", "-q", "main")
    command(repo, "git", "merge", "--squash", head)
    merge = commit(repo, "chore(alpha): release v1.2.4")
    command(repo, "git", "push", "-q", "origin", "main")
    gh.pr.update(merged=True, state="closed", merge_commit_sha=merge)
    write(repo, "later.txt", "Later main change\n")
    later = commit(repo, "docs: advance main")
    command(repo, "git", "push", "-q", "origin", "main")
    gh.main = later
    return base, head, merge, gh


@pytest.mark.parametrize("draft", [True, False])
def test_tag_exact_merge_sha_and_retry_preserves_release_text(repo, monkeypatch, draft):
    _, _, merge, gh = merged_release(repo, monkeypatch)
    for index in range(100):
        gh.releases[f"other/v{index}"] = {"tag_name": f"other/v{index}", "draft": True}
    assert tagging.tag_release(7, merge, root=repo) == "https://example.test/draft"
    assert gh.tags["alpha/v1.2.4"]["object"]["sha"] == merge
    assert gh.releases["alpha/v1.2.4"]["target_commitish"] == merge
    assert gh.releases["alpha/v1.2.4"]["draft"] is True
    assert gh.releases["alpha/v1.2.4"]["body"] == "No shipped changes since the previous release."
    gh.releases["alpha/v1.2.4"].update(body="Human edited text", draft=draft)
    writes = len(gh.writes)
    assert tagging.tag_release(7, merge, root=repo) == "https://example.test/draft"
    assert len(gh.writes) == writes
    assert gh.releases["alpha/v1.2.4"]["body"] == "Human edited text"
    assert gh.releases["alpha/v1.2.4"]["draft"] is draft


def test_tag_conflict_does_not_move_tag(repo, monkeypatch):
    _, _, merge, gh = merged_release(repo, monkeypatch)
    gh.tags["alpha/v1.2.4"] = {"object": {"type": "commit", "sha": gh.main}}
    with pytest.raises(opening.ReleaseError, match="will not be moved"):
        tagging.tag_release(7, merge, root=repo)
    assert gh.writes == []
    assert gh.tags["alpha/v1.2.4"]["object"]["sha"] == gh.main


def test_tag_partial_failure_retries_draft_only(repo, monkeypatch):
    _, _, merge, gh = merged_release(repo, monkeypatch)
    gh.fail_release = True
    with pytest.raises(opening.ReleaseError, match="Draft creation failed"):
        tagging.tag_release(7, merge, root=repo)
    assert gh.tags["alpha/v1.2.4"]["object"]["sha"] == merge
    gh.fail_release = False
    assert tagging.tag_release(7, merge, root=repo) == "https://example.test/draft"
    assert len([p for p, _ in gh.writes if p == "git/refs"]) == 1


def test_draft_creation_recovers_lost_success_response(repo, monkeypatch):
    _, _, merge, gh = merged_release(repo, monkeypatch)

    def lost_response(root, repo_name, path, **kwargs):
        result = gh.api(root, repo_name, path, **kwargs)
        if path == "releases":
            raise opening.ReleaseError("Lost successful draft response")
        return result

    monkeypatch.setattr(tagging, "gh_api", lost_response)
    assert tagging.tag_release(7, merge, root=repo) == "https://example.test/draft"
    assert tagging.tag_release(7, merge, root=repo) == "https://example.test/draft"
    assert len([p for p, _ in gh.writes if p == "releases"]) == 1


def test_tag_rejects_latest_main_and_changed_reviewed_tree(repo, monkeypatch):
    _, _, merge, gh = merged_release(repo, monkeypatch)
    with pytest.raises(opening.ReleaseError, match="does not identify"):
        tagging.tag_release(7, gh.main, root=repo)
    gh.pr["head"]["sha"] = gh.main
    with pytest.raises(opening.ReleaseError, match="reviewed PR tree"):
        tagging.tag_release(7, merge, root=repo)
    assert gh.writes == []

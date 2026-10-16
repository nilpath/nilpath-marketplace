"""Behavior of nstack's draft pull request publisher.

Uses a real local git repository with a bare "origin" remote and a fake `gh`
executable on PATH that records every call, so no network or GitHub account
is involved.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "plugins" / "nstack" / "skills" / "nstack-flow" / "scripts" / "publish_draft.py"

FAKE_GH = textwrap.dedent(
    r'''
    #!/usr/bin/env python3
    import json, os, subprocess, sys
    args = sys.argv[1:]
    state_path = os.environ["FAKE_GH_STATE"]
    with open(os.environ["FAKE_GH_LOG"], "a") as log:
        log.write(json.dumps(args) + "\n")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {"prs": []}
    def save():
        json.dump(state, open(state_path, "w"))
    def opt(name):
        return args[args.index(name) + 1]
    def head_sha(branch):
        if os.environ.get("FAKE_GH_HEAD"):
            return os.environ["FAKE_GH_HEAD"]
        return subprocess.run(["git", "rev-parse", f"origin/{branch}"], capture_output=True, text=True).stdout.strip()
    if args[:2] == ["auth", "status"]:
        sys.exit(int(os.environ.get("FAKE_GH_AUTH_EXIT", "0")))
    if args[:2] == ["pr", "list"]:
        head = opt("--head")
        print(json.dumps([{k: p.get(k, False) for k in ("number", "url", "isDraft", "baseRefName", "isCrossRepository")}
                          for p in state["prs"] if p["head"] == head and p["state"] == "OPEN"]))
        sys.exit(0)
    if args[:2] == ["pr", "create"]:
        if os.environ.get("FAKE_GH_CREATE_EXIT"):
            print("could not create pull request", file=sys.stderr)
            sys.exit(int(os.environ["FAKE_GH_CREATE_EXIT"]))
        number = len(state["prs"]) + 1
        state["prs"].append({
            "number": number,
            "url": f"https://github.com/acme/demo/pull/{number}",
            "isDraft": "--draft" in args and os.environ.get("FAKE_GH_DRAFT", "1") == "1",
            "head": opt("--head"),
            "baseRefName": opt("--base"),
            "state": "OPEN",
        })
        save()
        print(state["prs"][-1]["url"])
        sys.exit(0)
    if args[:2] == ["pr", "view"]:
        ref = args[2]
        pr = next(p for p in state["prs"] if str(p["number"]) == ref)
        print(json.dumps({"number": pr["number"], "url": pr["url"], "isDraft": pr["isDraft"],
                          "headRefOid": head_sha(pr["head"]), "baseRefName": pr["baseRefName"], "state": pr["state"]}))
        sys.exit(0)
    print("fake gh: unsupported command " + " ".join(args), file=sys.stderr)
    sys.exit(99)
    '''
).lstrip()


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def origin_git(repo, *args: str) -> str:
    # Bare repositories are addressed explicitly so safe.bareRepository=explicit is respected.
    return git(repo["tmp"], f"--git-dir={repo['origin']}", *args)


@pytest.fixture
def repo(tmp_path):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-b", "main")
    git(work, "config", "user.email", "test@example.com")
    git(work, "config", "user.name", "Test")
    (work / "README.md").write_text("demo\n")
    git(work, "add", "README.md")
    git(work, "commit", "-m", "Initial commit")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-u", "origin", "main")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    body = tmp_path / "body.md"
    body.write_text("## Summary\nDemo change.\n")
    env = dict(os.environ)
    env.update({
        "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
        "FAKE_GH_STATE": str(tmp_path / "gh-state.json"),
        "FAKE_GH_LOG": str(tmp_path / "gh-log.jsonl"),
        "NSTACK_PUBLISH_RETRY_DELAY": "0",
        "NSTACK_PUBLISH_ATTEMPTS": "2",
    })
    return {"work": work, "origin": origin, "env": env, "body": body, "tmp": tmp_path}


def feature_commit(repo, branch="nstack/demo"):
    work = repo["work"]
    git(work, "switch", "-c", branch)
    (work / "feature.txt").write_text("feature\n")
    git(work, "add", "feature.txt")
    git(work, "commit", "-m", "Add feature")


def publish(repo, *extra, base="main") -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", base, "--title", "Demo", "--body-file", str(repo["body"]), *extra],
        cwd=repo["work"], env=repo["env"], capture_output=True, text=True,
    )
    return proc.returncode, json.loads(proc.stdout)


def gh_calls(repo) -> list[list[str]]:
    log = Path(repo["env"]["FAKE_GH_LOG"])
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def test_creates_and_verifies_a_draft_pull_request(repo):
    feature_commit(repo)
    code, data = publish(repo)
    assert code == 0, data
    head = git(repo["work"], "rev-parse", "HEAD")
    assert data["action"] == "created"
    assert data["is_draft"] is True
    assert data["head_sha"] == head
    assert data["url"] == "https://github.com/acme/demo/pull/1"
    assert origin_git(repo, "rev-parse", "nstack/demo") == head
    create = next(c for c in gh_calls(repo) if c[:2] == ["pr", "create"])
    assert "--draft" in create
    assert create[create.index("--base") + 1] == "main"


def test_never_runs_ready_merge_or_auto_merge(repo):
    feature_commit(repo)
    publish(repo)
    commands = {tuple(c[:2]) for c in gh_calls(repo)}
    assert commands <= {("auth", "status"), ("pr", "list"), ("pr", "create"), ("pr", "view")}
    assert not any("--auto" in c or "ready" in c or "merge" in c for c in gh_calls(repo))


def test_reuses_an_existing_open_pull_request(repo):
    feature_commit(repo)
    publish(repo)
    (repo["work"] / "feature.txt").write_text("feature v2\n")
    git(repo["work"], "commit", "-am", "Refine feature")
    code, data = publish(repo)
    assert code == 0, data
    assert data["action"] == "existing"
    assert data["number"] == 1
    assert data["head_sha"] == git(repo["work"], "rev-parse", "HEAD")
    assert sum(1 for c in gh_calls(repo) if c[:2] == ["pr", "create"]) == 1


def test_refuses_to_publish_from_the_base_branch(repo):
    code, data = publish(repo)
    assert code == 1
    assert data["error"]["code"] == "on_base_branch"
    assert gh_calls(repo) == []


def test_refuses_when_there_is_nothing_to_publish(repo):
    git(repo["work"], "switch", "-c", "nstack/empty")
    code, data = publish(repo)
    assert data["error"]["code"] == "nothing_to_publish"


def test_stops_before_pushing_when_gh_is_unauthenticated(repo):
    feature_commit(repo)
    repo["env"]["FAKE_GH_AUTH_EXIT"] = "1"
    code, data = publish(repo)
    assert data["error"]["code"] == "gh_unauthenticated"
    remote_branches = origin_git(repo, "branch", "--list")
    assert "nstack/demo" not in remote_branches


def test_rejected_push_is_not_forced(repo):
    feature_commit(repo)
    publish(repo)
    other = repo["tmp"] / "other"
    subprocess.run(["git", "clone", "-b", "nstack/demo", str(repo["origin"]), str(other)], check=True, capture_output=True)
    git(other, "config", "user.email", "o@example.com")
    git(other, "config", "user.name", "Other")
    (other / "other.txt").write_text("other\n")
    git(other, "add", "other.txt")
    git(other, "commit", "-m", "Someone else's commit")
    git(other, "push")
    remote_head = origin_git(repo, "rev-parse", "nstack/demo")
    (repo["work"] / "feature.txt").write_text("diverged\n")
    git(repo["work"], "commit", "-am", "Diverge")
    code, data = publish(repo)
    assert data["error"]["code"] == "push_rejected"
    assert origin_git(repo, "rev-parse", "nstack/demo") == remote_head


def test_reports_create_failure_after_push(repo):
    feature_commit(repo)
    repo["env"]["FAKE_GH_CREATE_EXIT"] = "1"
    code, data = publish(repo)
    assert data["error"]["code"] == "pr_create_failed"
    assert data["error"]["branch"] == "nstack/demo"


def test_verification_fails_when_head_does_not_match(repo):
    feature_commit(repo)
    repo["env"]["FAKE_GH_HEAD"] = "0" * 40
    code, data = publish(repo)
    assert data["error"]["code"] == "verification_failed"
    assert "does not match local HEAD" in data["error"]["message"]


def test_verification_fails_when_created_pull_request_is_not_a_draft(repo):
    feature_commit(repo)
    repo["env"]["FAKE_GH_DRAFT"] = "0"
    code, data = publish(repo)
    assert data["error"]["code"] == "verification_failed"
    assert "not a draft" in data["error"]["message"]


def test_reports_uncommitted_changes_left_behind(repo):
    feature_commit(repo)
    (repo["work"] / "README.md").write_text("local edit\n")
    code, data = publish(repo)
    assert code == 0, data
    assert data["uncommitted_changes_left"] is True


def test_ignores_a_fork_pull_request_that_reuses_the_branch_name(repo):
    feature_commit(repo)
    Path(repo["env"]["FAKE_GH_STATE"]).write_text(json.dumps({"prs": [{
        "number": 1, "url": "https://github.com/acme/demo/pull/1", "isDraft": False,
        "head": "nstack/demo", "baseRefName": "main", "state": "OPEN", "isCrossRepository": True,
    }]}))
    code, data = publish(repo)
    assert code == 0, data
    assert data["action"] == "created"
    assert data["number"] == 2
    assert data["is_draft"] is True
    view = next(c for c in gh_calls(repo) if c[:2] == ["pr", "view"])
    assert view[2] == "2"

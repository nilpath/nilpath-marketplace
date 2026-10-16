#!/usr/bin/env python3
"""Publish the current branch as a draft pull request, then verify it.

Pushes without force, reuses an existing open pull request for the branch
instead of creating a duplicate, creates new pull requests only as drafts, and
verifies the result against the local HEAD. It never marks a pull request
ready, merges, enables auto-merge, or watches CI.

Usage:
  publish_draft.py --base BRANCH --title TITLE --body-file PATH [--remote NAME]

Prints one JSON object. Exit 0 on a verified result, non-zero otherwise.
Standard library only; Python 3.11+.
"""

from __future__ import annotations

import sys

if sys.version_info < (3, 11):  # pragma: no cover
    sys.stdout.write('{"ok": false, "error": {"code": "unsupported_python", "message": "Python 3.11+ required."}}\n')
    sys.exit(1)

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path


class PublishError(Exception):
    def __init__(self, code: str, message: str, repair: str = "", **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.repair = repair
        self.extra = extra


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, proc.stdout, proc.stderr)
    return proc


def git(*args: str, check: bool = True) -> str:
    return run(["git", *args], check=check).stdout.strip()


def gh_json(*args: str):
    proc = run(["gh", *args], check=False)
    if proc.returncode != 0:
        raise PublishError(
            "gh_failed",
            f"`gh {' '.join(args[:2])}` failed: {(proc.stderr or proc.stdout).strip()}",
            "Check the gh error above, then publish again.",
        )
    return json.loads(proc.stdout or "null")


def preflight(base: str, remote: str, body_file: Path) -> tuple[str, str, bool]:
    if git("rev-parse", "--is-inside-work-tree", check=False) != "true":
        raise PublishError("not_a_repo", "The current directory is not inside a git repository.")
    branch = git("branch", "--show-current", check=False)
    if not branch:
        raise PublishError("detached_head", "HEAD is detached.", "Create or switch to a feature branch first.")
    if branch == base:
        raise PublishError(
            "on_base_branch",
            f"The current branch is the base branch '{base}'.",
            "Create a feature branch for the change, commit there, and publish again.",
        )
    if remote not in git("remote").split():
        raise PublishError("unknown_remote", f"Git remote '{remote}' does not exist.")
    if not body_file.is_file():
        raise PublishError("missing_body", f"Pull request body file not found: {body_file}.")
    base_ref = None
    for candidate in (f"refs/remotes/{remote}/{base}", f"refs/heads/{base}"):
        if run(["git", "rev-parse", "--verify", "--quiet", candidate], check=False).returncode == 0:
            base_ref = candidate
            break
    if base_ref is None:
        raise PublishError("unknown_base", f"Base branch '{base}' was not found locally or on '{remote}'.")
    ahead = int(git("rev-list", "--count", f"{base_ref}..HEAD"))
    if ahead == 0:
        raise PublishError(
            "nothing_to_publish",
            f"'{branch}' has no commits ahead of '{base}'.",
            "Commit the verified change first.",
        )
    dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
    if shutil.which("gh") is None:
        raise PublishError("gh_missing", "The GitHub CLI (gh) is not installed.", "Install gh and authenticate.")
    if run(["gh", "auth", "status"], check=False).returncode != 0:
        raise PublishError("gh_unauthenticated", "gh is not authenticated.", "Run `gh auth login`, then publish again.")
    return branch, git("rev-parse", "HEAD"), dirty


def push(remote: str, branch: str) -> None:
    proc = run(["git", "push", "--set-upstream", remote, f"{branch}:{branch}"], check=False)
    if proc.returncode != 0:
        raise PublishError(
            "push_rejected",
            f"git push failed: {(proc.stderr or proc.stdout).strip()}",
            "Reconcile the branch with its remote without force-pushing, or ask the user how to proceed.",
        )


def find_open_pr(branch: str) -> dict | None:
    # `gh pr list --head` matches the branch name only, so fork pull requests that
    # happen to reuse the same name must be filtered out explicitly.
    prs = gh_json(
        "pr", "list", "--head", branch, "--state", "open",
        "--json", "number,url,isDraft,baseRefName,isCrossRepository",
    )
    same_repo = [pr for pr in prs if not pr.get("isCrossRepository")]
    if len(same_repo) > 1:
        raise PublishError(
            "ambiguous_pr", f"Several open pull requests use '{branch}' as head.", "Ask the user which one to use."
        )
    return same_repo[0] if same_repo else None


def pr_number_from_url(text: str) -> str | None:
    for token in reversed(text.split()):
        if "/pull/" in token:
            number = token.rstrip("/").rsplit("/", 1)[-1]
            if number.isdigit():
                return number
    return None


def verify(pr_ref: str, head: str, must_be_draft: bool) -> dict:
    attempts = int(os.environ.get("NSTACK_PUBLISH_ATTEMPTS", "5"))
    delay = float(os.environ.get("NSTACK_PUBLISH_RETRY_DELAY", "2"))
    view: dict = {}
    for attempt in range(attempts):
        view = gh_json("pr", "view", pr_ref, "--json", "number,url,isDraft,headRefOid,baseRefName,state")
        if view.get("headRefOid") == head:
            break
        if attempt + 1 < attempts:
            time.sleep(delay)
    problems = []
    if view.get("headRefOid") != head:
        problems.append(f"pull request head {view.get('headRefOid')} does not match local HEAD {head}")
    if view.get("state") != "OPEN":
        problems.append(f"pull request state is {view.get('state')}")
    if must_be_draft and view.get("isDraft") is not True:
        problems.append("pull request is not a draft")
    if problems:
        raise PublishError(
            "verification_failed", "; ".join(problems) + ".", "Inspect the pull request before reporting it.", pr=view
        )
    return view


def publish(base: str, title: str, body_file: Path, remote: str) -> dict:
    branch, head, dirty = preflight(base, remote, body_file)
    push(remote, branch)
    existing = find_open_pr(branch)
    if existing is None:
        proc = run(
            [
                "gh", "pr", "create", "--draft",
                "--base", base, "--head", branch,
                "--title", title, "--body-file", str(body_file),
            ],
            check=False,
        )
        if proc.returncode != 0:
            raise PublishError(
                "pr_create_failed",
                f"gh pr create failed: {(proc.stderr or proc.stdout).strip()}",
                "The branch is pushed; report the failure and the branch name.",
                branch=branch,
            )
        pr_ref = pr_number_from_url(proc.stdout)
        if pr_ref is None:
            raise PublishError(
                "verification_failed",
                f"gh pr create did not report a pull request URL: {proc.stdout.strip()!r}.",
                "Inspect the repository's pull requests before reporting a result.",
                branch=branch,
            )
        action = "created"
    else:
        pr_ref = str(existing["number"])
        action = "existing"
    view = verify(pr_ref, head, must_be_draft=action == "created")
    result = {
        "ok": True,
        "action": action,
        "url": view.get("url"),
        "number": view.get("number"),
        "is_draft": view.get("isDraft"),
        "base": view.get("baseRefName"),
        "branch": branch,
        "head_sha": head,
        "uncommitted_changes_left": dirty,
    }
    if action == "existing":
        note = "An open pull request already existed for this branch; the push updated it instead of creating another."
        if view.get("baseRefName") != base:
            note += f" Its base is '{view.get('baseRefName')}', not '{base}'."
        result["note"] = note
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish the current branch as a verified draft pull request.")
    parser.add_argument("--base", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args(argv)
    try:
        result = publish(args.base, args.title, Path(args.body_file), args.remote)
    except PublishError as exc:
        error = {"code": exc.code, "message": exc.message, "repair": exc.repair, **exc.extra}
        print(json.dumps({"ok": False, "error": error}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

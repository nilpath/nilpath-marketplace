"""Open a draft release PR without touching the caller's checkout."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")


class ReleaseError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReleaseError(message)


def run(root, *args, input=None):
    result = subprocess.run(args, cwd=root, input=input, capture_output=True)
    if result.returncode:
        raise ReleaseError(f"{shlex.join(args)} failed\n{result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def git(root, *args):
    return run(root, "git", "--no-pager", *args).decode().strip()


def blob(root, sha, path):
    return run(root, "git", "show", f"{sha}:{path}")


def version_field(raw):
    fields = re.findall(rb"^version: ([^\r\n]+)\r?$", raw, re.M)
    require(len(fields) == 1, "Expected exactly one top-level version scalar")
    value = fields[0].decode("ascii", errors="replace")
    require(VERSION.fullmatch(value), f"Invalid semantic version {value!r}")
    return value


def bump_version(version, bump):
    require(VERSION.fullmatch(version), f"Invalid semantic version {version!r}")
    require(bump in {"major", "minor", "patch"}, "BUMP must be major, minor or patch")
    major, minor, patch = map(int, version.split("."))
    return {
        "major": f"{major + 1}.0.0",
        "minor": f"{major}.{minor + 1}.0",
        "patch": f"{major}.{minor}.{patch + 1}",
    }[bump]


def replace_version(raw, target):
    current = version_field(raw)
    require(VERSION.fullmatch(target), "Invalid target version")
    return re.sub(rb"(?m)^(version: )" + re.escape(current.encode()) + rb"(\r?)$",
                  lambda m: m[1] + target.encode() + m[2], raw, count=1)


@dataclass(frozen=True)
class ReleaseBump:
    plugin: str
    previous_version: str
    target_version: str

    def __post_init__(self):
        require(NAME.fullmatch(self.plugin), "Invalid plugin name")
        require(VERSION.fullmatch(self.previous_version) and VERSION.fullmatch(self.target_version),
                "Invalid semantic version")
        require(self.target_version in {bump_version(self.previous_version, b) for b in ("major", "minor", "patch")},
                "Expected one major, minor or patch bump")

    @property
    def source(self):
        return f"src/plugins/{self.plugin}/plugin.yaml"

    @property
    def tag(self):
        return f"{self.plugin}/v{self.target_version}"

    @property
    def branch(self):
        return f"release/{self.plugin}-v{self.target_version}"


def repository(root):
    value = run(root, "gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner").decode().strip()
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value), "Invalid GitHub repository")
    return value


def gh_api(root, repo, path, *, missing=False, **fields):
    args = ["gh", "api", f"repos/{repo}/{path}"]
    for key, value in fields.items():
        args += ["-F" if isinstance(value, bool) else "-f",
                 f"{key}={str(value).lower() if isinstance(value, bool) else value}"]
    result = subprocess.run(args, cwd=root, capture_output=True)
    if missing and result.returncode and b"HTTP 404" in result.stderr:
        return None
    require(result.returncode == 0, f"gh api {path} failed\n{result.stderr.decode(errors='replace')}")
    return json.loads(result.stdout)


def open_release(plugin, bump, root=ROOT):
    require(NAME.fullmatch(plugin), "Invalid PLUGIN")
    require(bump in {"major", "minor", "patch"}, "BUMP must be major, minor or patch")
    git(root, "fetch", "origin", "refs/heads/main:refs/remotes/origin/main")
    base = git(root, "rev-parse", "origin/main")
    deployed = set(git(root, "ls-tree", "-r", "--name-only", base).splitlines())
    require({"tools/open_release.py", "tools/prepare_release.py", "tools/tag_release.py"} <= deployed
            and "tools/release.py" not in deployed,
            "origin/main does not support simple releases yet. Merge the replacement before running make release.")
    source = f"src/plugins/{plugin}/plugin.yaml"
    previous = version_field(blob(root, base, source))
    release = ReleaseBump(plugin, previous, bump_version(previous, bump))
    require(not git(root, "tag", "--list", release.tag)
            and not git(root, "ls-remote", "--tags", "origin", f"refs/tags/{release.tag}"),
            f"Tag {release.tag} already exists. Inspect it; nothing was overwritten.")
    require(not git(root, "branch", "--list", release.branch), f"Local branch {release.branch} already exists. Inspect it; nothing was overwritten.")
    require(not git(root, "ls-remote", "--heads", "origin", f"refs/heads/{release.branch}"),
            f"Remote branch {release.branch} already exists. Inspect its PR; nothing was overwritten.")
    repo = repository(root)
    push = ("-c", "core.hooksPath=/dev/null", "push", "origin",
            f"--force-with-lease=refs/heads/{release.branch}:", f"HEAD:refs/heads/{release.branch}")
    create_pr = ("gh", "pr", "create", "--repo", repo, "--base", "main",
                 "--head", release.branch, "--draft", "--title",
                 f"chore({plugin}): release v{release.target_version}", "--body",
                 f"Release {release.tag}.\n\nThe release workflow prepares the files before human review.")
    work = Path(tempfile.mkdtemp(prefix="nilpath-open-release-")) / "work"
    try:
        git(root, "-c", "core.hooksPath=/dev/null", "worktree", "add", "-b", release.branch, str(work), base)
    except ReleaseError as exc:
        raise ReleaseError(f"{exc}\nNo push was attempted. Inspect git worktree list and "
                           f"git branch --list {release.branch}. Temporary location {work}.") from exc
    try:
        expected = replace_version(blob(root, base, source), release.target_version)
        (work / source).write_bytes(expected)
        git(work, "add", "--", source)
        require(git(work, "diff", "--cached", "--name-only", base) == source
                and blob(work, "", source) == expected, "The staged change is not the selected version scalar")
        git(work, "-c", "core.hooksPath=/dev/null", "commit", "-m", f"chore({plugin}): release v{release.target_version}")
        require(not git(work, "ls-remote", "--heads", "origin", f"refs/heads/{release.branch}"),
                f"Remote branch {release.branch} appeared during preparation. Inspect it; nothing was overwritten.")
        git(work, *push)
        url = run(work, *create_pr).decode().strip()
    except (ReleaseError, OSError) as exc:
        command = shlex.join(create_pr)
        recovery_push = shlex.join(["git", "-C", str(work), *push])
        raise ReleaseError(
            f"{exc}\nRetained worktree {work} and branch {release.branch}.\n"
            f"Inspect with git -C {shlex.quote(str(work))} status.\n"
            f"Inspect the remote with git ls-remote --heads origin refs/heads/{release.branch}.\n"
            f"If committed and the remote is absent, retry {recovery_push}\n"
            f"If the remote already matches local HEAD, skip the push.\n"
            f"If not committed, inspect and commit only {source} first.\n"
            f"After confirming the push, find an existing PR with gh pr list --repo {repo} --head {release.branch}.\n"
            f"If none exists, run {command}\n"
            f"After recovery, remove the worktree with git worktree remove {shlex.quote(str(work))}."
        ) from exc
    try:
        git(root, "worktree", "remove", str(work))
        work.parent.rmdir()
    except (ReleaseError, OSError) as exc:
        raise ReleaseError(f"Draft PR created at {url}.\n{exc}\n"
                           f"Inspect git worktree list and {work.parent}; do not create another PR. "
                           f"If the worktree remains, remove it with git worktree remove {shlex.quote(str(work))}.") from exc
    return url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--bump", required=True, choices=("major", "minor", "patch"))
    args = parser.parse_args()
    try:
        print(open_release(args.plugin, args.bump))
    except (ReleaseError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()

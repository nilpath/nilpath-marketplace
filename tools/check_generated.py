"""Reject ordinary PR changes to release-owned generated files."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "buildkit/src"))
from buildkit.ownership import owns


PROPOSAL_MARKER = "<!-- nilpath-release-proposal:"
BOT = "github-actions[bot]"
BOT_ID = 41898282


def proposal_candidate(pr, repository):
    return (pr.get("user", {}).get("login") == BOT and pr["user"].get("id") == BOT_ID
            and (pr.get("head", {}).get("repo") or {}).get("full_name") == repository
            and (pr["head"].get("ref", "").startswith("release/proposal-")
                 or PROPOSAL_MARKER in (pr.get("body") or "")))


def git(root, *args):
    result = subprocess.run(["git", "--no-pager", *args], cwd=root, capture_output=True)
    if result.returncode:
        raise ValueError(f"git failed: {result.stderr.decode(errors='replace')}")
    return result.stdout.decode().strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base-sha", required=True)
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[0-9a-f]{40}", args.base_sha):
            raise ValueError("Invalid base SHA")
        if os.environ.get("GITHUB_EVENT_PATH"):
            event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())
            pr = event["pull_request"]
            if pr["head"]["sha"] != git(args.root, "rev-parse", "HEAD"):
                raise ValueError("PR head mismatch")
            if proposal_candidate(pr, event["repository"]["full_name"]):
                print("Generated-file validation deferred to the required release-plan job for this bot-owned proposal.")
                return 0
        merge_base = git(args.root, "merge-base", args.base_sha, "HEAD")
        paths = git(args.root, "diff", "--no-renames", "--name-only", "-z", merge_base, "HEAD").split("\0")
        changed = sorted(path for path in paths if owns(path))
        if changed:
            raise ValueError("Ordinary PR changes build-owned paths:\n" + "\n".join(changed))
        print("Ordinary PR preserves build-owned paths.")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"check-generated: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

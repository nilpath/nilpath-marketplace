"""Tag the exact reviewed squash merge and create a draft without replacing release text."""

from __future__ import annotations

import argparse
from urllib.parse import quote

from open_release import ROOT, SHA, ReleaseError, blob, gh_api, git, repository, require
from prepare_release import changelog_offset, release_request


def existing_release(root, repo, tag):
    matches = []
    page = 1
    while True:
        releases = gh_api(root, repo, f"releases?per_page=100&page={page}")
        matches.extend(release for release in releases if release["tag_name"] == tag)
        if len(releases) < 100:
            break
        page += 1
    require(len(matches) <= 1, f"Multiple releases use tag {tag}; inspect them before retrying")
    return matches[0] if matches else None


def tag_release(pr_number, merge_sha, *, root=ROOT):
    require(SHA.fullmatch(merge_sha), "Expected an exact merge commit SHA")
    repo = repository(root)
    pr = gh_api(root, repo, f"pulls/{pr_number}")
    require(pr["merged"] and pr["merge_commit_sha"] == merge_sha, "PR does not identify this merged commit")
    require(pr["base"]["ref"] == "main"
            and pr["base"]["repo"]["full_name"] == repo and pr["head"]["repo"]["full_name"] == repo,
            "Expected a same-repository release merged to main")
    git(root, "fetch", "--no-tags", "origin", merge_sha, pr["head"]["sha"])
    parents = git(root, "show", "-s", "--format=%P", merge_sha).split()
    require(len(parents) == 1, "Expected a squash merge with one parent")
    base = parents[0]
    require(git(root, "rev-parse", f"{merge_sha}^{{tree}}")
            == git(root, "rev-parse", pr["head"]["sha"] + "^{tree}"), "Merge differs from the reviewed PR tree")
    release = release_request(root, base, merge_sha)
    require(pr["head"]["ref"] == release.branch, "Not a release request branch")
    old = blob(root, base, "CHANGELOG.md")
    reviewed = blob(root, merge_sha, "CHANGELOG.md")
    offset = changelog_offset(old)
    prefix = old[:offset] + f"## {release.tag}\n\n".encode()
    suffix = old[offset:]
    require(reviewed.startswith(prefix) and reviewed.endswith(suffix), "Missing reviewed release notes or changed changelog history")
    notes = reviewed[len(prefix):len(reviewed) - len(suffix)].decode().strip()
    require(notes, "Empty reviewed release notes")
    tag_path = "git/ref/tags/" + quote(release.tag, safe="")

    def verify_tag(ref):
        obj = ref["object"]
        for _ in range(10):
            if obj["type"] != "tag":
                break
            obj = gh_api(root, repo, f"git/tags/{obj['sha']}")["object"]
        require(obj["type"] == "commit" and obj["sha"] == merge_sha,
                f"Tag {release.tag} already points elsewhere. It will not be moved.")

    existing = gh_api(root, repo, tag_path, missing=True)
    if existing is None:
        try:
            gh_api(root, repo, "git/refs", ref="refs/tags/" + release.tag, sha=merge_sha)
        except ReleaseError:
            existing = gh_api(root, repo, tag_path, missing=True)
            if existing is None:
                raise
    verify_tag(existing or gh_api(root, repo, tag_path))
    found = existing_release(root, repo, release.tag)
    if found is not None:
        return found["html_url"]
    try:
        result = gh_api(root, repo, "releases", tag_name=release.tag, target_commitish=merge_sha,
                        name=release.tag, body=notes, draft=True)
    except ReleaseError:
        result = existing_release(root, repo, release.tag)
        if result is None:
            raise
    return result["html_url"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--merge-sha", required=True)
    args = parser.parse_args()
    try:
        print(tag_release(args.pr, args.merge_sha))
    except (ReleaseError, OSError) as exc:
        parser.exit(1, f"{exc}\nRe-run jobs after resolving the failure. Existing tags and release text are never overwritten.\n")


if __name__ == "__main__":
    main()

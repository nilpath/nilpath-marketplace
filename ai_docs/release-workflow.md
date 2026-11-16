# Release a plugin

Merge ordinary source changes first. Then open a version-bump PR with
`make release`. The Release workflow prepares the selected plugin's changelog
and installation files in that PR. After review and squash merge, it tags the
merge commit and creates a draft GitHub release. Publishing remains manual.

## Set up releases

Deploy the release scripts and workflows to `main` before using the command.
The command checks fetched `origin/main`, not an unmerged local implementation.
Use an existing `gh` login with permission to push branches and open PRs.

Install the declared dependencies:

```sh
make install
```

The Make targets use `~/.virtualenvs/nilpath-marketplace` by default.
Set `VENV=/path/to/environment` to use another environment.
The dependency declarations supply git-cliff 2.13.1 and editable buildkit.
CI uses Python 3.11 and uv 0.12.23.

Configure the `main` ruleset to require `pr-title`, `test-static`, an up-to-date
branch, one human approval, approval of the latest push, and squash merging.
The old `release-plan` check is no longer used.

GitHub Actions needs contents-write permission for preparation and tagging.
It never approves or merges PRs. Bot-generated PR updates can require a writer
to select **Approve workflows to run** before ordinary CI starts. Do not treat
an approval-required run as a passing check.

## Develop an ordinary change

1. Edit shipping sources under `src/`.
2. Run `make test-static`.
3. Commit sources without version bumps or generated installation files.

`make check` validates sources. Tests inspect a fresh temporary build, so pending
source changes do not require changing committed `dist/`.
The low-level `nilpath-build check` compares all committed output with a full
fresh build. It is not the ordinary PR gate or a per-plugin release check.
Likewise, `make build` is a full render, not the release command.

CI validates the PR title, checks generated paths in a separate step, and runs
static tests. The guard covers `dist/`, `.claude-plugin/marketplace.json`,
`.agents/plugins/marketplace.json`, and `.github/plugin/marketplace.json`.
It rejects additions, deletions, renames, content changes, and mode changes.

Check the guard locally against a fetched base:

```sh
sh tools/check_generated.sh origin/main
```

Use a Conventional Commit PR title, such as
`feat(nstack): add a verification skill`. Allowed types are `feat`, `fix`, `perf`,
`refactor`, `revert`, `docs`, `deps`, `chore`, `ci`, `test`, `style`, and `build`.

```sh
tools/pr_conventions.sh --title "feat(nstack): add a verification skill"
```

The title script also accepts `PR_NUMBER=123 tools/pr_conventions.sh` to fetch a
title through `gh`. Keep the PR title as the squash commit title.
Git-cliff uses commit messages for release notes, not to choose version bumps.

Model-backed tests remain separate. Run `make test-behavioral` with the required
credentials when checking skill behavior. Static CI needs no model credentials.

## Open and review a release PR

Choose one plugin and one semantic-version increment:

```sh
make release PLUGIN=nstack BUMP=minor
```

`BUMP` accepts `major`, `minor`, or `patch`. The command reads the selected
plugin's current version from fetched `origin/main`. It uses a temporary worktree
to commit only the source `version:` change, pushes a new branch, and opens a
draft PR. Your current branch, index, and uncommitted files stay unchanged.
Existing release branches are not overwritten.
An existing target tag also stops the request before preparation.

The workflow uses that version bump as its release request:

1. Wait for preparation to add the changelog, current-version README fields,
   and generated files.
2. Inspect the selected plugin's version, notes, and output for each client.
3. Approve workflow execution if GitHub requests it.
4. Wait for `pr-title` and `test-static` to pass on the prepared head.
5. Mark the PR ready, obtain human approval of the latest push, and squash-merge.
6. Inspect the tag and draft GitHub release, then publish the release manually.

Do not add features, tooling changes, or hand-edited generated content to a
release PR. Merge those changes separately before opening the release PR.
The release check accepts only one version bump and its exact derived files.
A branch name alone never permits generated-file changes.

Preparation renders all sources into a temporary directory, then copies only
the selected plugin's client directories and registry entries into the PR.
Other plugins' installed bytes and versions remain unchanged even if their
sources have pending changes. Marketplace metadata is preserved.
The changelog's heading and introduction stay at the top, followed by the new
release section and unchanged historical sections.

The notes use the previous plugin-version tag as their history anchor.
Before the first tag, `.release/baselines.toml` supplies the reviewed historical
anchor. It is not a second version authority.
Notes include selected-plugin and shared-rendering changes, excluding changes
that affect only another plugin. Existing changelog history stays intact.

Marketplace-metadata releases, unanchored initial releases, multi-plugin batches,
and automatic publication are not supported by this command.

## Recover a failed release

Read the command's error before retrying. Push and PR creation are separate
operations. If a push succeeds but PR creation fails, the command reports the
retained branch and a recovery command. It never force-pushes or silently chooses
a different version.

For workflow failures, use GitHub Actions' **Re-run jobs** action after resolving
the reported problem. Preparation fails if the PR head or base changes underneath
it rather than replacing newer work. If main has advanced, open a fresh release
request from current main instead of rebasing generated output by hand.

To replace a stale request, close its PR first. Inspect the old release branch
and confirm that its work can be discarded. Remove any retained temporary
worktree, then delete both the local and remote release branches before running
the command again. Closing a PR alone does not delete those branches. The command
does not delete them for you.

Branch writes use explicit Git ref preconditions. Creation requires an absent
remote branch. Preparation requires the captured PR head and adds a child commit.
The `--force-with-lease` arguments enforce those conditions, not permission to
replace existing history.

Tags use `<plugin>/v<version>` and identify the merged PR's `merge_commit_sha`.
They do not trigger preparation. Retrying tagging accepts an existing tag only
when it already points at that merge commit. A conflicting tag fails and is
never moved. Existing draft or published release text is not overwritten.

GitHub can reject a release against a historical commit when its workflows differ
from current main. The workflow does not substitute a newer commit or add broader
credentials to work around that failure.

## Trust and verification

Preparation uses `pull_request_target` with protected-main scripts, dependencies,
and templates. It reads the PR as Git data and imports only its validated version
scalar. It never executes candidate code with write credentials.
Ordinary PR CI remains read-only. No PAT, GitHub App, or mutable-branch workflow
dispatch is needed.

Direct script tests use disposable Git repositories, git-cliff, and fake GitHub
responses. These checks do not establish hosted workflow behavior. A live
preparation, CI-approval, and tagging exercise requires a separately authorized
release.

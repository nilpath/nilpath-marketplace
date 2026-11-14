# Prepare and review component releases

Ordinary changes merge without manual version bumps. The Release workflow opens
one draft preparation PR for independently versioned plugins and marketplace
metadata. After review and a valid squash merge, it creates component tags and
draft GitHub releases. Publishing is always manual.

## Activate the workflows

Before relying on automation, review these repository settings yourself.
The implementation does not change settings.

1. Enable GitHub Actions for the repository.
2. Review **Allow GitHub Actions to create and approve pull requests**.
   The observed settings use read-default workflow permissions and
   `can_approve_pull_request_reviews=false`. The writer requests explicit job
   permissions, but repository policy can still prohibit PR creation.
3. Configure the `pr-title`, `test-static`, and `release-plan` CI jobs as required checks.
   Require branches to be up to date before merging. Do not rebase or update a
   release proposal onto a different input.
4. Require human review and squash merges onto `main`. Configure the default
   squash commit title to use the PR title.

PRs opened, synchronized, or reopened by `GITHUB_TOKEN` wait for a user with
write access to click **Approve workflows to run**. Token pushes alone do not
trigger CI. No PAT or GitHub App is required by these workflows.
Do not mistake an approval-required run for a passing check.

## Develop an ordinary change

Install the declared local dependencies before the first check:

```sh
make install
export PATH="$HOME/.virtualenvs/nilpath-marketplace/bin:$PATH"
```

`make install` supplies git-cliff 2.13.1 through `pyproject.toml`, along with the
Python test dependencies and editable buildkit. Make targets put the selected
`VENV/bin` on PATH. Export that same directory when running the release CLI
directly. A separate global or CI-only git-cliff installation is not needed.
Use `make install VENV=/path/to/new/environment` for an isolated installation.

1. Edit shipping sources under `src/`.
2. Run `make build check`.
3. Run `make test-static`.
4. Include source and generated output in the ordinary PR.

Never edit `dist/` or the three root registries directly.
`src/plugins/<plugin>/plugin.yaml` owns each plugin's current version.
`src/marketplace.yaml` owns the marketplace version.
Buildkit generates all client manifests and registries.
Keep current-version README fields, but do not change historical nstack or
pstack references.

CI checks committed output before any rebuild.
It uses Python 3.11 and the existing Make targets with a command-line `VENV`
override. The workflows pin uv 0.12.23 and git-cliff 2.13.1.
The root `uv.lock` does not lock buildkit's installation. These installs are not
claimed to be frozen.

Model-backed behavioral tests remain separate.
Run `make test-behavioral` when changing skill behavior, with the required model
credentials. Add or update fixtures under `tests/fixtures/behavioral/` for changed
delegation behavior. Static CI does not use model credentials.

### Use a Conventional Commit PR title

The `pr-title` job validates titles when a PR opens, receives commits, reopens,
or is edited. It does not run on pushes or manual workflow dispatches.
Use `<type>[optional scope][optional !]: <summary>`, for example
`feat(nstack): add a verification skill` or `fix!: remove obsolete behavior`.
Allowed types are `feat`, `fix`, `perf`, `refactor`, `revert`, `docs`, `deps`,
`chore`, `ci`, `test`, `style`, and `build`.

Check a title locally without credentials:

```sh
tools/pr_conventions.sh --title "feat(nstack): add a verification skill"
```

To fetch the title of an existing PR, run
`PR_NUMBER=123 tools/pr_conventions.sh`. This uses your existing `gh` login,
`GH_TOKEN`, or `GITHUB_TOKEN` without changing authentication settings.
The repository defaults to `GITHUB_REPOSITORY` or `nilpath/nilpath-marketplace`.
Set `GH_REPO` to override it.

Keep the validated PR title as the squash commit title when merging.
The commit type helps the release planner classify changes. This repository's
git-cliff configuration does not silently drop unconventional commits.
Ambiguous changes still require
explicit release decisions, even when their titles pass this check.

## Review a preparation PR

After an ordinary merge, the Release workflow evaluates changes after each
component's accepted baseline.

1. Open the bot's draft preparation PR.
2. If the proposal needs decisions, follow the next section before reviewing versions.
3. Inspect source versions, exact README fields, changelog sections, generated
   manifests, reviewed decisions, and `.release/plan.json`.
4. Click **Approve workflows to run**.
5. Wait for successful `pr-title`, `test-static`, and `release-plan` checks on the exact
   proposal head.
6. Approve that exact head. Mark the PR ready yourself when appropriate, then
   squash-merge it without changing its input parent or checked tree.
7. Inspect the resulting draft GitHub releases. Publish them manually when ready.

The workflow never marks a PR ready, reviews it, merges it, or publishes a release.
Any new main commit makes an older proposal's recorded input stale.
Let a new preparation supersede it rather than rebasing or force-pushing it.
Automatic refresh carries decisions from an unchanged regenerated proposal.
If you edited decisions, dispatch an explicit resolution with that exact head.
Resolution can carry still-applicable decisions after main advances. It first
verifies the old proposal's immutable edits against its own input, then validates
the exact component and commit decisions against the new input.
Unrelated edits, conflicting accepted decisions, changed heads, and non-ancestor
inputs fail instead of discarding work.
Discovery ignores human PRs, fork PRs, and unrelated bot PRs even if they copy a
proposal marker or branch name. A malformed bot-owned same-repository proposal
still fails. Explicit resolution never accepts a foreign PR.

To request preparation explicitly:

```sh
gh workflow run release.yml --ref main -f mode=prepare
```

## Resolve an ambiguous proposal

A blocked proposal contains suggestions and decision requests, not partial
version bumps. Its `release-plan` check fails until regeneration resolves every
request.

Add entries to the proposal's `.release/decisions.toml`:

```toml
[[decision]]
component = "nstack"
commit = "<full commit SHA>"
bump = "patch"
reason = "Changes wording, not the invocation contract."
```

Allowed increments are `patch`, `minor`, and `major`. Use `none` only with a
reason for excluding that exact component and commit.
For a new plugin, `initial` confirms the authored initial source version.
Each affected commit before its first release needs its own exact-SHA
confirmation. One `initial` decision does not approve later source changes.
Keep accepted decisions. Do not edit the generated plan, source versions, or
other proposal files to resolve a question.

Dispatch with the exact edited proposal head:

```sh
gh workflow run release.yml --ref main -f mode=prepare \
  -f proposal_pr=123 -f expected_head='<full-head-SHA>'
```

The writer reads decisions only from that head. It creates a replacement branch
and draft PR rather than force-pushing over your work. It closes the old PR only
after the replacement exists. A resolution containing only `none` decisions can
persist without a version, tag, or release.
Its merged transaction still needs exact-head human approval and CI before
completion, as described below.

The planner applies this policy:

| Evidence | Proposal |
| --- | --- |
| Direct `fix`, `docs`, `perf`, or `refactor` | Patch unless breaking |
| Direct `feat` or added skill or agent | Minor |
| Stable breaking change | Major |
| Feature on `0.0.x`, or any pre-1.0 breaking change | Explicit decision |
| Unknown message, conflicting scope, or removal | Explicit decision |
| Shared build, defaults, or client changes with shipped differences | Component-specific decision |
| Shared change with identical shipped trees | Explain as unchanged |
| Root CI, tests, and repository-only documentation | No plugin bump |
| New plugin | Confirm authored initial version |

Plugins do not cascade versions to dependencies or marketplace metadata.
Marketplace metadata changes require their own explicit decision.
The adapter owns increment arithmetic. Git-cliff parses and renders the selected
commits, including unconventional messages. A skipped commit requires an explicit
component-bound decision and reason.
The note date comes from the immutable input commit, so regeneration is repeatable.
Deleting or renaming a component's source identity fails rather than inventing a
current version. Keep source metadata for a removal release, or review a separate
component-identity migration.

## Retry draft creation

The release identity includes component, version, merged SHA, and plan ID.
Tags use `<component>/v<version>`. They point at the reviewed squash merge, never
the current main tip.

```sh
gh workflow run release.yml --ref main -f mode=drafts \
  -f proposal_pr=123 -f merged_sha='<full-merged-SHA>'
```

The writer verifies the human approval, exact-head CI run and check provenance,
recorded input parent, exact merged-tree equality, plan, source, and generated
metadata before creating a tag. It creates tags explicitly, then invokes
`gh release create --draft --verify-tag` with the exact merged SHA.

A matching tag or draft is reused. Human-edited release text is preserved.
A matching published release is a terminal no-op. Conflicting tags or unowned
releases fail. API errors, incomplete pagination, stale identities, and missing
checks fail visibly. A later proposal is blocked by an incomplete prior release
transaction. Retry that transaction first.

Before the first draft, the full review, CI, merge, and generated-file checks are
mandatory. Completed releases retain their immutable plan, merge, source, tag,
and ownership-marker identity. They do not require old CI records to remain
available or old content to be regenerated by today's updater.
The actual tag ref is authoritative. GitHub does not use `target_commitish`
when the tag already exists.

Decision-only transactions use one bot-authored completion comment on their
merged proposal PR instead of a release receipt. The reserved
`nilpath-release-complete` marker binds its format version, repository, PR number,
checked head, merged SHA, and plan ID. The writer creates it only after the full
first-time validation and confirms it through the comments API. Future preparation
requires that receipt. Merely merging a decision-only plan does not complete it.
Matching receipts are no-ops on retry, including when a write succeeded but its
response or confirmation failed. Historical review and CI records can then
disappear without blocking preparation.

Do not delete or copy completion comments. A missing receipt requires a `drafts`
retry with the original review and CI evidence still available. A receipt with a
login or ID that does not exactly match GitHub Actions is ignored before the
workflow reads a reserved marker. An exact bot-owned receipt with a different
identity, or multiple exact bot-owned reserved receipt comments, fails rather
than being adopted or overwritten. If the evidence is gone before completion,
or an exact bot-owned receipt is corrupted, stop for a separately reviewed
repair. The workflow does not create substitute version tags or releases for
decision-only plans.

GitHub can refuse release creation for a historical target whose workflow files
differ from the default branch. Its release API can require workflow-write
permission, which `GITHUB_TOKEN` cannot receive. The workflow fails visibly in
that case. It does not substitute current main, move the reviewed tag, introduce
another credential, or publish a release.

No workflow uploads release assets, overwrites assets, deletes branches, or
publishes releases. An interrupted branch or draft creation can resume without
force pushes. Proposal branches bind the plan identity, not a workflow attempt.
If a replacement exists but commenting on or closing the old PR failed, a fresh
preparation can finish automatic supersession after verifying both exact heads.
For an edited decision resolution, retry with the original PR and expected head.
The old proposal can be draft or ready.

Artifacts still bind the workflow run and attempt. Start a fresh dispatch or
rerun all jobs. Rerunning only the failed writer cannot reuse an artifact from
an earlier attempt. GitHub concurrency can replace an older pending run, so use
the explicit `drafts` dispatch if an automatic release-merge run did not finish.

## Inspect provenance locally

```sh
PYTHONPATH=tools/buildkit/src ~/.virtualenvs/nilpath-marketplace/bin/python tools/release.py plan
PYTHONPATH=tools/buildkit/src ~/.virtualenvs/nilpath-marketplace/bin/python tools/release.py check
# On a proposal branch, check the exact proposal against current main.
PYTHONPATH=tools/buildkit/src ~/.virtualenvs/nilpath-marketplace/bin/python tools/release.py check-proposal \
  --base-sha "$(git rev-parse origin/main)"
make build check
make test-static
```

Run `plan` on main history. It cannot infer GitHub merge state from a local
proposal commit. On a proposal branch, inspect `.release/plan.json` and use
`check-proposal` instead. Fetch current main before that check.
`check` validates historical provenance, including deletion of either versioned
or decision-only plans. CI selects `check-proposal` explicitly for release PRs.
It rejects extra commits, rebases, stale inputs, unexpected trees, and unsafe
file modes. A deliberately bypassed invalid merge still fails draft validation
and requires a separately reviewed repair. There is no history-reset bypass.

`tools/release.py` provides the local `plan`, `prepare`, `bundle`, `check`, and
`check-proposal` commands and the GitHub `snapshot` and `write` commands.
The read-only planner discovers components through buildkit configuration.
The separate inspect and write jobs invoke `snapshot` and `write` from the
dispatcher revision with `python -S`, without buildkit or YAML dependencies.
Local planning and GitHub writes share the strict plan and deterministic
file-update contract. The write job downloads one data bundle. It never executes
candidate code, installs candidate dependencies, extracts a candidate archive,
or applies arbitrary files.
Checkout credentials are not persisted. No workflow uses `pull_request_target`.

### Historical compatibility contract

Schema 1 fixes the generated metadata byte contract, including changelog
insertion, version fields, README selectors, JSON formatting, and decision
serialization. Active proposals and first-time draft retries use that fixed
contract against their immutable input, not the current generator.
They remain usable after the current git-cliff pin or updater changes.
The writer checks the input's policy digest and literal git-cliff pin without
executing historical code. It permits decision edits only at the explicitly
selected head.

First-time completion compares every file path, blob, and mode against the input
plus the schema's exact updates. Workflow files, verifier code, build code, and
dependency declarations must therefore remain unchanged in the proposal.
Passing jobs from modified PR-owned verifiers do not substitute for this check.
Human approval and Actions workflow, run, attempt, job, check-app, suite, URL, and
exact-head association checks still apply.

The schema-1 contract helpers are compatibility code, not the current generation
policy. Do not change their byte behavior when changing the generator.
Fresh artifacts still require current tools and policy, and generation that
violates the fixed schema-1 contract fails explicitly. Unknown schemas and
unsupported historical policies fail too. A byte-contract or schema change needs
a separately reviewed compatibility repair before automation can handle those
new bytes. The writer never silently regenerates an old proposal in place.

The initial `.release/baselines.toml` anchors are the last commits that established
each current source version. Review them as historical provenance, not another
version authority. Adoption creates no version bumps, tags, or releases.
Existing changelog bytes remain below `<!-- release-legacy-boundary -->`,
including the old Unreleased section. The generator does not reinterpret them.

Local tests use temporary Git repositories, actual git-cliff, fake GitHub API
responses, and a fake `gh` executable. They do not prove Linux-hosted execution,
repository settings, or live bot PR and release creation.

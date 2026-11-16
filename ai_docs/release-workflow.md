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
2. Run `make test-static`.
3. Include sources only in the ordinary PR.

Never edit `dist/` or the three root registries directly.
`src/plugins/<plugin>/plugin.yaml` owns each plugin's current version.
`src/marketplace.yaml` owns the marketplace version.
Buildkit generates all client manifests and registries.
Keep current-version README fields, but do not change historical nstack or
pstack references.

CI rejects ordinary changes to build-owned paths before rendering a preview.
This includes additions, deletions, renames, byte changes, and executable modes.
Tests inspect a fresh temporary render, not committed installation files.
`make check` validates sources. The low-level `nilpath-build check` still compares
the committed snapshot with a fresh build for release verification.
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
3. Inspect source versions, exact README fields, changelog sections, all generated
   changes, reviewed decisions, and `.release/plan.json`.
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
Preparation performs one full regeneration. Every component whose generated
content changes must have a release version, including shared changes and
marketplace-owned registry fields. A changed component with `none` or an
unresolved decision blocks the full release rather than publishing unversioned
content. Decision-only transactions do not regenerate installation files.
Older shared commits retain their committed-output evidence. Source-only shared
commits use pending rendered impact and conservative component/SHA decisions.
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
make test-static
```

Run `plan` on main history. It cannot infer GitHub merge state from a local
proposal commit. On a proposal branch, inspect `.release/plan.json` and use
`check-proposal` instead. Fetch current main before that check.
`check` validates historical provenance, including deletion of either versioned
or decision-only plans. In CI, the `pr-title` job runs
`python3 -S tools/check_generated.py --base-sha "$BASE_SHA"` alongside title
validation. The standalone check compares the PR head to its merge base with
the current base SHA and rejects ordinary changes to build-owned paths.
A copied branch name or marker does not grant a generated-file exception.
Only same-repository proposals owned by the exact GitHub Actions bot identity
defer generated-file validation to the independently required `release-plan`
job. The guard reports that deferral without claiming to validate the output.
The `test-static` job only installs dependencies and tests fresh source output.

The `release-plan` job uses `check-pr` with the PR event to select release-history
checks or exact proposal validation. It does not repeat the ordinary
generated-file check. Exact proposal validation rejects extra commits, rebases,
stale inputs, unexpected trees, and unsafe file modes.
A deliberately bypassed invalid merge still fails draft validation
and requires a separately reviewed repair. There is no history-reset bypass.

Local `tools/release.py` commands are `plan`, `prepare`, `bundle`, `check`,
`check-pr`, `check-proposal`, and `verify-bundle`.
The GitHub commands are `snapshot` and `write`.
The read-only planner discovers components through buildkit configuration.
The separate inspect and write jobs invoke `snapshot` and `write` from the
dispatcher revision with `python -S`, without renderer or YAML dependencies.
A separate read-only verifier installs dispatcher-owned dependencies and
reconstructs the complete transaction from a clean immutable input checkout.
Input and dispatcher renderer identities must match. A mismatch requires a fresh
dispatch. The verifier compares decisions, plan, payloads, and modes before
uploading a separate verified artifact.
The writer receives that artifact ID from the verifier job dependency, not from
the candidate bundle. It checks repository, input, dispatcher and renderer
identities, workflow run and attempt, decisions, and plan ID before writing.
It never renders templates, executes candidate code, installs candidate
dependencies, or applies arbitrary files.
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

The schema-1 helpers remain frozen compatibility code.
Fresh schema-2 plans bind canonical generated put and delete operations into the
plan ID. Each operation records the path, Git mode, and content digest.
Deletions record the expected input identity. Bundles carry put bytes.
Historical schema-2 validation uses recorded operations and Git blobs, not
historical executable code or today's renderer. Every unaffected path, mode,
and blob remains identical to the input. Unknown schemas and unsupported
historical policies fail. The writer never regenerates an old proposal in place.

The initial `.release/baselines.toml` anchors are the last commits that established
each current source version. Review them as historical provenance, not another
version authority. Adoption creates no version bumps, tags, or releases.
Existing changelog bytes remain below `<!-- release-legacy-boundary -->`,
including the old Unreleased section. The generator does not reinterpret them.

Local tests use temporary Git repositories, actual git-cliff, fake GitHub API
responses, and a fake `gh` executable. They do not prove Linux-hosted execution,
repository settings, or live bot PR and release creation.

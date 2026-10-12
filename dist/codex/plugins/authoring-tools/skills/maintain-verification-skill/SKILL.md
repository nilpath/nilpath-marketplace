---
name: maintain-verification-skill
description: Keeps a project's verification skill and feature map aligned with the app through source checks and live verification, shipping proven corrections in one pull request. Invoke explicitly to maintain a verification skill or audit its feature map and driving harness.
---

# Maintain a verification skill

Maintain a project-local verification skill created by the `create-verification-skill` skill or any compatible skill with launch/drive instructions and a feature map. Cover every mapped feature from source and live behavior; do not turn the pass into a sentence-by-sentence documentation audit.

Invoke explicitly with `$maintain-verification-skill`. Do not load this workflow automatically. It may commit, push, and open one pull request for verified corrections.

## Outcomes

Report exactly one outcome:

- **clean**: every feature received source and live coverage; no corrections need shipping. No new branch or PR.
- **changed**: complete coverage and proven corrections shipped in one PR. Report the PR URL and evidence location.
- **blocked**: required coverage could not finish or corrections could not ship safely. Do not initiate a PR while blocked. Report the exact blocker, coverage achieved, evidence location, and any local edits, commit, remote branch, or PR already created by a partially successful publishing attempt.

A skipped or failed journey is not a successful verification. Do not claim `clean` or `changed` from partial coverage.

## Edit scope and prerequisites

Only edit the selected verification skill's own directory: its `SKILL.md`, `features/`, and owned harness scripts or supporting files. Never edit product code during maintenance. Classify a mismatch as doc drift or a product regression; do not rewrite the map to hide a regression.

Use a scratch location outside the skill directory for concise run notes: features and entry points covered, unreachable prerequisites, confirmed drift, and outcome. Do not commit those notes or proof artifacts.

Protect unrelated working-tree changes. If the target skill already has uncommitted changes, use a direct chat question to the user (wait for their reply before continuing) to resolve ownership before editing; otherwise stop as blocked. Never revert, stash, or include someone else's work to make the run proceed.

Shipping requires Git, an appropriate remote/base branch, authenticated `gh` access, and the `git-commits` skill from the git-tools plugin. Do not invent substitute publishing tools or silently downgrade `changed` to uncommitted edits. Read-only inspection may proceed without publishing capabilities, but report `blocked` if needed corrections cannot be shipped.

## 1. Locate the target

Resolve the project root, then inspect `.claude/skills/`, `.github/skills/`, and `.agents/skills/` there. A candidate has a `SKILL.md` containing launch/drive instructions and a feature map, usually under `features/`. Names commonly start with `verify-`, but inspect the content rather than relying only on the prefix.

Resolve symlinks and deduplicate candidates pointing to the same physical directory. If a target resolves outside the project, obtain explicit scope confirmation before editing it. Several distinct candidates require a direct chat question to the user (wait for their reply before continuing) to select one. With none, stop and point to the `create-verification-skill` skill instead of inventing a target.

Maintain the selected directory in place, even if it belongs to another supported harness. Do not migrate it, change its invocation policy, or create duplicate installations. If its driving tools are unavailable in the active environment, diagnose a harness gap or report the missing capability; never assume an editor-specific tool exists.

## 2. Check index hygiene

Read the feature-map README and glob its sibling files. Reconcile missing, extra, duplicate, and dead entries. Keep this lightweight; do not generate a separate inventory. Preserve valid feature journeys and discover their actual preconditions.

## 3. Read the source

Obtain a source-backed summary and live-verification recipe for every feature file. Use read-only subagents only for substantial, separable investigations where they are useful and available. Independent readers may run concurrently. For a small map or unavailable delegation, read the source directly with the same coverage and return shape:

- Feature summary
- Source entry points with file/line citations
- Likely drift, or none
- One concise live-verification recipe

Readers never drive the app and never edit files. Do not assign multiple readers to re-check the same clean evidence. The coordinator owns all app interaction and edits.

## 4. Reconcile the recipes

Confirm every feature file has a returned summary, whether from a reader or direct inspection. Merge overlapping recipes into as few app states as practical. Spot-check cited drift without re-proving clean source claims.

Sweep recent changes for user-facing surfaces missing from the map. Require a concrete source path before calling a feature missing. Include confirmed missing features in the map and the live coverage.

## 5. Run the live pass

Live verification is required even when source looks clean. Follow the selected skill's Launch section: one long-lived instance driven serially for servers and UIs, or a fresh isolated session per drive for short-lived CLI/TUI programs.

Exercise every mapped feature at least once and cover its documented user entry points. One convenient entry point does not verify another. Hold these invariants throughout successful drives, failures, and retries:

1. **Doctor before driving.** Health-check before the first drive, each fresh session, and after every failed drive or surprising result. If the doctor cannot detect a wedged UI on an otherwise healthy process, reset to a known state or relaunch before continuing.
2. **Evidence survives cleanup.** Preserve evidence already captured and check that it still exists at the named location after every cleanup. Never assume teardown left it intact.
3. **Clean failed-iteration residue.** Nothing a drive started outlives its usefulness. Stop only processes or sessions the run owns and remove its scratch state, including after a stuck or exited session. For a shared instance, clean owned residue, not the user's instance. Never kill by process name.

If a doctor failure is caused by skill drift, fix it within edit scope, restart only what the fix invalidated, and retry once before calling the pass `blocked`.

Label an unreachable feature `verified-unreachable` only with the concrete unmet prerequisite (authentication, entitlement, OS, or external state) and the route actually attempted. A missing prerequisite in the map is drift. This label records evidence of the blocker, not a passed journey; if it prevents required coverage, report `blocked`.

Re-drive every harness fix live before shipping. Complete final teardown after the last drive, including all re-proofs, and confirm the evidence remains. Never stop after a failed iteration without running the applicable cleanup.

## 6. Triage

- **Doc drift:** wrong or missing user-facing instructions. Correct the map to match established behavior and verified prerequisites.
- **Harness gap:** working behavior cannot be driven by the harness. Fix only the skill-owned harness. Supplied scripts must be executable, their invocation documented in the skill body, and fixes re-driven live.
- **Product gap:** the app's behavior is actually broken. Report the regression and observed evidence to the user; keep product fixes out of this PR. Never weaken an expected behavior simply to make verification pass.

Do not publish partial corrections while required coverage is blocked.

## 7. Ship or stop

For `clean` or `blocked`, report the outcome and coverage honestly without creating a PR. For proven corrections with complete coverage:

1. Re-read every changed skill file. Confirm each change is within edit scope and supported by evidence; check helper executability and documented invocation.
2. Check branch, working-tree, and index state. Use a dedicated correction branch and the intended base, or reuse an appropriate existing correction branch/PR. Ensure the PR would contain only these corrections, not unrelated commits. If branch isolation or unrelated staged work prevents safe shipping, report `blocked` rather than altering someone else's work.
3. Use the `git-commits` skill to review and commit the exact corrected files. Stage explicit file paths only, excluding notes, evidence, and unrelated changes. Do not use blanket staging.
4. Push the correction branch without force-pushing. Use `gh` to check for an existing PR for that branch and intended base. Reuse it or create one PR for these proven corrections, including coverage, evidence locations, and any reported product gaps.
5. Confirm the remote PR exists and includes the correction commit before reporting `changed`. A commit, push, or PR failure is `blocked`, not success; report what already happened so the user can recover. After an ambiguous publishing response, inspect remote state before any retry. Never blindly retry PR creation or delete a partially created PR to make the outcome look clean.

Do not create multiple PRs in one pass or perform destructive git recovery. Proof artifacts remain available after shipping or a blocked result.

## Attribution

Adapted from [pstack's maintain-verification-skill](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/maintain-verification-skill/SKILL.md), copyright (c) 2026 Lauren Tan, under the [MIT license](./LICENSE).

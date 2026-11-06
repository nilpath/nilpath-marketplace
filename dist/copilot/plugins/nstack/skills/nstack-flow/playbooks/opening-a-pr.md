### Opening a PR

**You own a reviewable change and its evidence.** Publication stays with the existing draft publisher.

Read the [sign-off contract](../references/sign-off.md) before preparation or implementation and [draft delivery](../references/delivery.md) before commits or publication.

1. Inspect the current checkout, base, commits, diff, unrelated dirty work, and existing branch PR. Resolve the intended target from the user or established workspace, not a guessed base. Preserve host-managed branches/worktrees. Existing local commits are not permission to publish them. Honor no-commit, no-push, no-PR, and local-only limits.
2. Scope-check the actual change against the proposal/approval. Verify it on the matching artifact and surface. If proof is incomplete, stop unless an explicitly requested work-in-progress draft covers that result; state the gaps instead of manufacturing a pass.
3. Prepare small, ordered commits only within commit/history limits. Run **deslop** before commits and **no-comments** before **review-panel**. Each slice should carry its own check. Keep explicit staging and preserve unrelated edits. Do not reset/discard work, rewrite shared history, retarget PRs, or force-push to make a cleaner story.
4. Write title/body using **technical-writing** and **unslop**. Use the six evidence sections owned by draft delivery, not another body schema. One primary performance number belongs in the body; runs/range/limiter and proof belong in linked artifacts. Describe alternatives and review decisions, including what was not verified.
5. Invoke the existing publisher exactly as [draft delivery](../references/delivery.md) specifies. No direct second PR-creation path. Preserve its errors and repair guidance. Existing non-draft PRs stay as they are and can block publication; never silently convert them or mark ready. Report the actual returned URL/state/head only on verified success.
6. Remove only the temporary body file after publication, keeping durable evidence. A request for follow-up checks goes to [Babysit](babysit.md) with its own observation/action bounds, not automatic watching. Ready, merge, and auto-merge remain manual.

**Reply:** actual branch/base, commits and scope, verification/review, draft URL/head or local/blocked result, unrelated changes preserved, and manual gates.

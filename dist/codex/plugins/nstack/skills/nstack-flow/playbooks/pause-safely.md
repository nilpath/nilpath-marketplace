### Pause safely

**You own a recoverable stop.** This is an explicit pause request, not an inference from "going to bed" or "keep going".

Read the [sign-off contract](../references/sign-off.md) and [run accounting](../references/run-contract.md) before changing coordination state.

1. Stop dispatching new work. Ask owned workers to hold at a safe boundary and wait within a stated stop budget. Complete only an already-authorized atomic operation necessary for a safe stop. Unknown or unobservable workers remain unknown, not assumed cancelled. Use actual native handles, never process-name killing.
2. Preserve the current workspace, including unrelated dirty bytes. Do not stash, reset, create a WIP commit, push, publish, or delete resources merely to pause. Existing permission for an action is not a reason to perform it now. Keep evidence outside product and cleanup targets.
3. Record the pause and actual observations through run accounting when a store exists. Preserve reservations and uncertain effects. Write a revision-bound handoff naming intent, plan/store, actual proposal/decision locators, current branches/heads/dirty-content fingerprints, accepted/stale receipts, owned resources, unknown workers/effects, blockers, and the first safe next action. Point at the existing **show-me-your-work** trail rather than duplicating its decisions.
4. Read the saved handoff back. Confirm proof survives and identify what is on disk versus only in conversation. If stop confirmation or storage failed, report a partial pause explicitly. [Session pickup](session-pickup.md) owns later reconciliation, not blind resumption from this note.

**Reply:** handoff/store/evidence paths, preserved workspace state, confirmed and unknown stops, uncertain effects, and first action on resume. This is a pause, not a completion report.

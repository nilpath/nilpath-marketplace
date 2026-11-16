### Feature

**You own the design. Plan, review, verify.** Delegate implementation. Stay in the lead.

Read the [sign-off contract](../references/sign-off.md) before preparation or implementation.

1. `how` over the affected subsystem.
2. `architect` for parallel design exploration, explicitly assigned to return design only. Its runners produce scratch design artifacts, not product scaffolds or implementations. You retain approval and implementation ownership, even under an autonomy waiver.
3. Write the throughput checkpoint as four todo items. A dimension that genuinely does not apply (single file, no fan-out) keeps its item with `n/a: <reason>` rather than being dropped:
   - **Blocking first steps.** Gates run before fan-out.
   - **Independent workstreams.** Disjoint files, services, or layers parallelize. Shared writes serialize.
   - **Shared mutable state.** Default to splitting the target (the **separate-before-serializing-shared-state** principle skill). Serialize only for real invariants.
   - **Smallest safe decomposition.** If one worker is best, name why.
4. Present one proposal combining the design and execution plan per the sign-off contract. The throughput checkpoint is execution planning, not approval. Stop before product edits, scaffolds, shipping tests or harnesses, implementing delegates, and code-producing candidate-graft unless a matching approval or explicit waiver covers execution. A nested architect never owns a second checkpoint.
5. Within that authority, delegate code-writing to an `implementer` subagent (`implementer-hard` for the hardest changes) with the approved scope, exclusions, stop conditions, and success criteria. Name file paths, the data shape, and its organizing structure per **principle-model-the-domain** before logic. Choose a state machine over scattered booleans, a table or registry over branching, or a typed model over repeated shape assumptions where appropriate. When the implementation admits multiple valid shapes (error handling, abstraction layer, test structure), delegate via the **candidate-graft** skill instead, within the same authority, so the runners surface the alternatives and the cross-judge guards the pick. Mandatory within authorized implementation: no skip-with-reason escape, and Laziness Protocol does not override it (the gain is review separation, not lines saved). A subagent forbidden to spawn satisfies this by owning the diff directly with the same review separation. No "standing by" reply that waits on a nested agent. Comments per **Comments**. Surgical edits, re-ground against the source for upstream-derived files. Port shared-primitive improvements to all approved consumers and verify each. Commit liberally within the user's limits, on a feature branch, never the base branch (`references/delivery.md`, section 1).
6. Verify on the matching surface. "Inconclusive" or wrong-surface is not a pass. Flag it.
7. Rebase into small, ordered commits within the user's history restrictions. Stack follow-ups.
   Use the **sequence-verifiable-units** principle skill, building, verifying, and committing each small unit before the next.
8. Run the **review-panel** skill on the full change. Scope-check each Act-on finding. Send in-scope corrective fixes to a fresh `implementer` with consolidated authority, then re-verify. Stop and re-present material changes not covered by approval or a grant. Optional cleanup does not expand scope.
9. Deliver a draft pull request per `references/delivery.md`, honoring independent no-push, no-PR, and local-only limits.

Code-coupled work (one feature, one migration) goes to a single owner with the checkpoint inline. That owner fans out internally after the blocking phase. Parent-level fan-out is for slices that produce independent artifacts (audits, cross-subsystem investigations, competing experiments). Rewrite the checkpoint at phase boundaries. Spawn a fresh owner rather than chaining interrupts.

**Reply:** what you built, what you chose and why, the throughput checkpoint, the review-panel outcome, open decisions. Tables for design alternatives.

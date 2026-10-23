# Architect runner prompt

The orchestrator passes this file to every parallel candidate runner during Phase B. It supplies the task, Phase A grounding artifacts, and assigned scratch output paths outside product source. Each candidate has its own directory.

You are producing one artifact-only candidate design. Read the [architect skill](../SKILL.md) in full first. This is a design-only assignment, not permission to run its implementation phases or own user sign-off. Output a type sketch, function signatures, module map, and rationale shaped per [`rationale-template.md`](rationale-template.md).

Write only the assigned scratch artifacts. Do not implement a production candidate, edit product source, configuration, tests, or documentation, create a product scaffold, commit, or publish. Diagnostic-only scratch copies may supply evidence. A worktree does not authorize production implementation. Return the package to the coordinator even if the outer task has an autonomy waiver.

Apply the following discipline. The orchestrator compares candidates on these axes to pick a base.

- Caller's usage first. Write the README-style usage and two or three real call sites before the types, then derive the type sketch from them. The usage is the spec. The two must agree, so reconcile the sketch to the usage, not the reverse.
- Make the proposal assessable. Show current and desired behavior, actual files and functions to change, a central illustrative diff, exclusions, alternatives, and observable checks. Label sketches and diffs as design artifacts, not applied changes.
- Data structures first. Get the core types right and the code becomes obvious. Trace each dominant access pattern through the proposed structure. If the answer is "we'll add a map / index / cache later," the structure is wrong.
- Interface depth. Compare the capability hidden behind the public surface relative to the size of that surface. Prefer a simple interface that pulls complexity into the callee, even when the implementation becomes less simple. Do not put transport or wire types on the public API. Parse into domain types behind the interface.
- Shared state: if two actors might both write, ask "what happens?" If the answer isn't "nothing," default to per-actor state with a merge at the read boundary, per the **separate-before-serializing-shared-state** principle skill.
- Make boundaries visible. `not implemented` errors for bodies, `// TODO` pseudocode for tricky logic, doc comments stating intent and invariants. A reader should trace data from input to output by reading types and signatures alone.
- Encode invariants in types: hard-to-misuse types > runtime checks > prose comments, per the **encode-lessons-in-structure** principle skill.
- Validate at boundaries, trust types inside, per the **boundary-discipline** principle skill. Business logic as pure functions. The shell stays thin.
- Single source of truth per invariant. Derive instead of sync.
- Idempotent state transitions where applicable, per the **make-operations-idempotent** principle skill. Ask what happens if the operation runs twice or crashes halfway.
- Short call chains. If tracing the flow needs more than three files, flatten the hierarchy, per the **laziness-protocol** and **minimize-reader-load** principle skills.

You are one of the parallel runners, each on a different model. Produce the best design your model can make. Don't hedge against the others. Differences between candidates are the signal used to pick a base and graft. Converging on a safe-looking middle defeats the exploration.

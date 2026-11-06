### Perf issue

**You own the measurement story.** Tie every fix to a measurement, not source-reading predictions.

Read the [sign-off contract](../references/sign-off.md) before preparation or implementation.

1. Capture a baseline trace on the matching control/verification surface using safe existing checks or disposable diagnostic copies. Vet the baseline and each later number with **benchmark-checklist**. Product instrumentation or shipping harness edits first need covering diagnostic approval, even if temporary.
2. Run **how** to ground hypotheses. Try the performance mantras in order, cheapest first: don't do unused work; don't repeat it; do it less; do it later; do it off the visible path; do it concurrently; do it cheaper. Stop when an earlier mantra meets the user's target. Do not claim a ceiling without measurement.
3. Plan from the trace. If the fix crosses a function boundary, use **architect** for design only. Present one cause/edit/measurement proposal and stop unless matching approval or an explicit scoped grant covers it. Include instrumentation, tests/harnesses, change scope, correctness gate, workload and delivery limits. One adequate proposal can cover diagnostics and the fix.
4. Within that authority, delegate to `implementer` or `implementer-hard` with actual approval context or evidence, scope, exclusions and stop conditions. Review the diff and capture a post-fix trace using the same workload, tuning and surface. Each attempt ends in proof before the next. Use [run accounting](../references/run-contract.md) for coordinated/recoverable attempts and **show-me-your-work** for decisions.
5. Parse and compare the actual artifacts, including work/errors, run count, variation and limiter. Wrong-surface or inconclusive evidence is not a pass. A regression or gain below noise must be reported honestly. Preserve paired evidence rather than only a quoted number.
6. Run **review-panel** on the covered change and re-verify in-scope fixes. Use [Opening a PR](opening-a-pr.md) within delivery limits. For sustained experiments, hand off to [Hillclimb](hillclimb.md) with its frozen metric/harness, budget and covering authority.

**Reply:** baseline/post-fix number, unit, delta/uncertainty, correctness evidence, artifact paths, review, and actual delivery or blocker.

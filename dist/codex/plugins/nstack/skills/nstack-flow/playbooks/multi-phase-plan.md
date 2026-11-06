### Multi-phase plan

**You own a plan a different coordinator can execute and verify.** Planning does not launch implementers.

Read the [sign-off contract](../references/sign-off.md) before preparation or implementation and [run accounting](../references/run-contract.md) for the unit graph and execution handoff.

1. Ground the affected systems with **how**, and **why** when ownership/layering changes. Capture safe baseline evidence. State the current behavior, desired outcome, quantified scope, constraints, unresolved risks, and falsifiable done predicate. Settle design forks with design-only **architect** or [Prototype](prototype.md) outside product source, not shipping scaffolds.
2. Write a plan in an assigned artifact directory outside the product tree. Put the caller's usage and target shapes before implementation details. Divide it into stable named units with dependencies, exclusive outputs, evidence inputs, actual edit locations, acceptance commands/outcomes, stop conditions, and integration order. Include pilot, verification, review, and delivery units where they are needed. Plan-only output does not imply commit/push/PR permission.
3. Make each unit independently checkable. Declare minimum real-surface and correctness proof rather than mandatory lanes, arbitrary cloud fixtures, or a passing type check as user-behavior proof. Name unavailable surfaces and how failure blocks acceptance. Risk-first sequencing is more useful than an exhaustive ceremony.
4. Validate the graph with the run-accounting helper's create boundary. Duplicate IDs, missing dependencies, cycles, and contradictory ownership must be corrected before handoff. Store the plan reference and exact source/decision pointers outside the product tree; do not claim a graph check validates consent or the prose design.
5. Present this plan as one proportionate implementation proposal and stop. Include scope/exclusions, budgets, evidence checks, risks, and requested actions. Approval of editing the plan is not execution approval. If an actual approval or explicit grant already covers executing these exact units, hand that evidence to [Orchestrate](orchestrate.md) without another checkpoint. Otherwise end with the plan and next approval decision.

**Reply:** plan and graph paths, designed usage/shape, unit dependencies, verification and delivery bounds, open questions, and whether execution is pending or covered. Do not imply work has started.

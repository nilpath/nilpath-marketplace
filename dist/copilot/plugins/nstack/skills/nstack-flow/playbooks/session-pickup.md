### Session pickup

Read the [sign-off contract](../references/sign-off.md) before preparation or implementation.

Resolve script paths from the absolute installed nstack-flow skill directory without changing the project working directory.

**You own the resume point. Read the prior trail, don't redo it.**

1. Locate the prior trail. An explicitly identified transcript or handoff through the host's available session evidence, or a pushed branch. Do not glob unrelated sessions or invent an unavailable transcript path. Read the metadata overview and last messages first, then scan back for the decision points. Parse a long transcript with the task tool with agent type `nstack:nstack-agent`, `[nstack role=judgment]` at the start of the description, and the brief as the prompt and keep the reduced timeline in the main thread (the **principle-guard-the-context-window** skill). Use its configured nstack role tag, per the Subagents section.
2. Reconstruct operational state. The branch and worktree, what already landed (`git log`, `git diff` against the base), the open todos, the decisions made. The prior trail is authoritative input for prior decisions. Recover the actual proposal and attributable approval before product continuation. Resist the bias to re-derive it.
3. Diff done vs pending. Compare what shipped against what was planned, name the resume point, do not re-run the prior repro or redo completed work. A "let me verify from scratch" pass means you're treating the trail as untrustworthy when it's authoritative.
4. Route the remaining work to the matching playbook and pick the verdict: continue the execution, ship a finished recommendation, ratify or override a prior conclusion, or postmortem a failed run. The pickup playbook ends here. The routed playbook owns the rest.
5. Verify the inherited claims against the original goal on the real artifact (the **principle-prove-it-works** skill). A passing prior self-report is not the proof.

**Reply:** where the prior agent stopped, what you inherited vs redid (ideally nothing redone), the resume point, and the outcome.

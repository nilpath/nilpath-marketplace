### Eval

Read the [sign-off contract](../references/sign-off.md) before preparation or implementation.

Resolve script paths from the absolute installed nstack-flow skill directory without changing the project working directory.

**You own the experiment design. Plan, blind, run, synthesize.**

**Non-negotiables for blinding:**

- No `eval`, `test`, `judge`, `experiment`, `rubric`, `score`, `compare`, `benchmark`, `candidate`, `arena`, or `candidate-graft` in any directory, file, or prompt the candidate sees.
- The candidate prompt looks like an organic user request. State the goal, not the meta.
- No chain-eliciting cues. Don't ask the candidate to list which skills, principles, or files they applied. Ask for design notes generally and grade chain-following from code shape, not self-report.
- Sanitize directory and slug names. Use project-shaped names a user might pick.
- Don't tell the candidate other candidates exist.
- The judge can know it's judging but sees outputs by sanitized label only, never by model name.
- Comparing two variants: one judge scores both sets in a single pass on one scale, blind to which set each came from.

**Steps:**

1. **Frame.** State what variant is under test and what behavior counts as success. Write the rubric (3-6 concrete criteria) for the judge only. Hold it back from candidates.
2. **Set up sanitized environments.** Per-candidate working dir with the variant in place. Plant any context an organic task would have: a project skeleton, the skills the candidate would naturally read.
3. **Author one organic prompt.** What a user would type. No leakage of what's being measured.
4. **Spawn N parallel candidates** using the configured runner seats per [candidate-graft's Phase B](../../candidate-graft/SKILL.md#phase-b-fan-out). Each works in its own sanitized dir. Same prompt to each. Use its configured nstack role tag, per the Subagents section.
5. **Spawn one blinded judge** on an independent configured judge seat per [candidate-graft's Phase C](../../candidate-graft/SKILL.md#phase-c-cross-judge). Judge sees outputs by sanitized label and the rubric, never a model name. Prefer another model family when available; otherwise report the same-family limitation.
6. **Verify the chain from transcripts, not self-report.** Read each identified candidate's tool events through the host's actual session evidence. Do not glob unrelated sessions. If child events are unavailable, mark protocol adherence unverified rather than use the parent's transcript. That crosses workspace boundaries and reads private chats from unrelated projects. Look at which files each candidate actually opened. Grade chain-following from the files it really read plus the shape of the code, never from the candidate's own claims.
7. **Read every candidate output yourself** end to end. Compare to the judge's verdict. Disagreement means a model is biased or the rubric is ambiguous. Synthesize.

**Reply:** variant under test, rubric, per-candidate notes, judge's verdict, your synthesis, and a recommendation for whether to promote the variant.

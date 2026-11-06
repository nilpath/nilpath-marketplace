# Isolated comparison protocol

This reference owns the isolation and blind-judging mechanics reused by
[candidate-graft](../SKILL.md) and [Eval](../../nstack-flow/playbooks/eval.md).
Each caller owns its outcome and authority. It does not invoke promotion.

1. State the artifact, common task, limits and output shape. Freeze a private
   rubric before runs. Runners see the task and only their own context, not the
   rubric or others' outputs. Use separate assigned scratch directories for
   design/diagnostic work; product-producing variants require covering approval
   even in isolated worktrees.
2. Use the available configured runner seats specified by the calling skill,
   with its role markers and launch syntax. A caller may substitute its design
   role. Do not set new model/effort values or invent seats. Launch all
   independent workers in one batch where supported; wait for all outputs to
   stop changing before judging. A missing output is a reported dropout.
3. Give one configured judge the frozen rubric and completed outputs by path
   label, never by model identity. Prefer another model family where available;
   otherwise state that independence limit. Judge each criterion explicitly.
   The parent reads every output end to end while judging runs.
4. Compare the independent scores and rationales against actual artifacts.
   Resolve disagreement with evidence or a clarified rubric, not a holistic
   average. Preserve the verdict, private mapping and trial evidence outside
   product source, subject to the caller's source/privacy limits.

Candidate-graft continues into base selection, grafting and verification
under its existing authority contract. Eval uses organic sanitized contexts,
reports output quality and only observed child protocol evidence, and stops
at a recommendation. A judge's verdict is neither approval nor proof of
unobserved tool behavior.

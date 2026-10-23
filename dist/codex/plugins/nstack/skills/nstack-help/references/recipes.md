# Prompts worth copying

Swap in the real paths, skills, and done checks. Informal wording works.

Code-changing prompts below propose and stop for approval by default. The [sign-off contract](../../nstack-flow/references/sign-off.md) owns consent and continuation. Read it before adapting approval or autonomy wording.

## Understand

- `$nstack-flow read <thread>. restate the underlying issue in your own words, in plain english.`
- `$nstack-flow investigate why <symptom>. give me what we know, what data you used, and your best hypotheses. don't change any code yet.`
- `use $how to understand <subsystem>. then use $why to find out why it broke recently.`
- `$nstack-flow read the decision log, find what's done on this branch, and continue. don't redo finished work.`

## Build

- Bug: `$nstack-flow <symptom>. repro first, then fix and verify.`
- Bug in an app: `$nstack-flow repro this with $verify-<app>. if it repros on main, fix it and show me a video as proof.` Use the project's actual verification skill command.
- Bug with a cheap test: `$nstack-flow repro <bug> first. if there's a cheap test path, $tdd it. then fix and rerun.`
- Feature: `$nstack-flow add <behavior>. <current output> stays byte-identical. verify both.`
- Refactor: `$nstack-flow move <code> into one module, zero behavior change. record the current output first and prove it's unchanged after.`
- Perf: `$nstack-flow <operation> takes <time> on <fixture>. trace it, fix the measured cause, show me before and after.`

## Design and plan

- `$nstack-flow compare a few scratch designs for <feature>. keep diagnostic-only reproductions outside the product tree. propose any product prototype separately for approval.`
- `$nstack-flow we need <feature>. $architect it for design only, and answer open questions with diagnostic-only reproductions outside product source. let me review before proceeding.`
- `$nstack-flow draft a tutorial in scratch for how i would use <new package> first. then explain why it beats the current one.`
- `ask $candidate-graft for a second opinion on this thread and our approach.`
- `$architect with checkpoint: design <change>. stop and show me before implementing.`

## Review and deliver

- `$review-panel the whole branch, but skeptically. don't change anything yet. no nitpicks unless it's a real bug or regression.` Read the dismissals too.
- `$swarm check every package under <dir> against its check script. one worker per package. one report.`
- `$nstack-flow finish <change> as a draft pr. small ordered commits, evidence in the description.` nstack does not babysit or merge the pull request.

## Away and back

- `$nstack-flow im going to bed. implement <goal> autonomously, without the default sign-off checkpoint, in a fresh worktree off <base>. done means <checks>. keep a decision log. don't ask me before committing. if you're truly stuck after a few hours, stop and write up why.` The explicit scoped implementation grant waives the default checkpoint, not stepping away. Unattended work routes through `figure-it-out`.
- `$show-me-your-work catch me up on what you did last night.` Read its Attention section first.

# Prompts worth copying

Swap in the real paths, skills, and done checks. Informal wording works.

## Understand

- `/nstack:nstack-flow read <thread>. restate the underlying issue in your own words, in plain english.`
- `/nstack:nstack-flow investigate why <symptom>. give me what we know, what data you used, and your best hypotheses. don't change any code yet.`
- `use /nstack:how to understand <subsystem>. then use /nstack:why to find out why it broke recently.`
- `/nstack:nstack-flow read the decision log, find what's done on this branch, and continue. don't redo finished work.`

## Build

- Bug: `/nstack:nstack-flow <symptom>. repro first, then fix and verify.`
- Bug in an app: `/nstack:nstack-flow repro this with /verify-<app>. if it repros on main, fix it and show me a video as proof.` Use the project's actual verification skill command.
- Bug with a cheap test: `/nstack:nstack-flow repro <bug> first. if there's a cheap test path, /nstack:tdd it. then fix and rerun.`
- Feature: `/nstack:nstack-flow add <behavior>. <current output> stays byte-identical. verify both.`
- Refactor: `/nstack:nstack-flow move <code> into one module, zero behavior change. record the current output first and prove it's unchanged after.`
- Perf: `/nstack:nstack-flow <operation> takes <time> on <fixture>. trace it, fix the measured cause, show me before and after.`

## Design and plan

- `/nstack:nstack-flow prototype a few options for <feature>. take screenshots or videos for me to compare.`
- `/nstack:nstack-flow we need <feature>. /nstack:architect it first, and answer open questions with prototypes. let me review before proceeding.`
- `/nstack:nstack-flow write a tutorial for how i would use <new package> first. then explain why it beats the current one.`
- `ask /nstack:candidate-graft for a second opinion on this thread and our approach.`
- `/nstack:architect with checkpoint: design <change>. stop and show me before implementing.`
- `/nstack:visual-plan turn the existing design for <change> into a local MDX review. show the proposed API and unresolved decisions. don't implement it.`

## Review and deliver

- `/nstack:review-panel the whole branch, but skeptically. don't change anything yet. no nitpicks unless it's a real bug or regression.` Read the dismissals too.
- `/nstack:swarm check every package under <dir> against its check script. one worker per package. one report.`
- `/nstack:nstack-flow finish <change> as a draft pr. small ordered commits, evidence in the description.` nstack does not babysit or merge the pull request.
- `/nstack:visual-recap explain this branch's actual changes in the local viewer. compare the API contracts and distinguish evidence from inference.`

## Away and back

- `/nstack:nstack-flow im going to bed. <goal> in a fresh worktree off <base>. done means <checks>. keep a decision log. don't ask me before committing. if you're truly stuck after a few hours, stop and write up why.` Unattended work routes through `figure-it-out`.
- `/nstack:show-me-your-work catch me up on what you did last night.` Read its Attention section first.

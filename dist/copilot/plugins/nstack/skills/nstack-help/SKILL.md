---
name: nstack-help
description: Guides users through nstack setup, nstack-flow, and picking the skill, playbook, or principle for a task. Invoke nstack-help explicitly with a question.
disable-model-invocation: true
---

# nstack help

Answer the user's question about nstack, hand them a prompt they can send, and link the file the answer came from. For a help question, don't start the work. The user asked how, and an nstack run spends real tokens, so let them send the prompt.

A message that asks for work, such as "use nstack to fix this bug", is not a help question. Read [`nstack-flow`](../nstack-flow/SKILL.md) and do the work under it.

This file maps questions to the skills and guide pages that hold the answers. Those files own the details. Read the file you route to before you quote it, and trust it when it disagrees with this map. The links here point into the installed plugin, which the user may not be able to open, so give the user the file's public copy: `https://github.com/nilpath/nilpath-marketplace/blob/main/src/plugins/nstack/` followed by its path. Source templates end in `.j2`: link `skills/<name>/SKILL.md.j2` for an installed `SKILL.md`, and check the source filename for other templates.

Commands below use this client's invocation syntax. Give the user prompts in that syntax, not pstack's command names.

## Find out what they need

Infer the need from the message and the conversation. A named situation, such as "which skill reviews a PR?", goes straight to its section. If the need is still unclear, ask one multiple-choice question with these options, then answer only the section they pick:

- Get set up
- Start a task with `/nstack:nstack-flow`
- Pick a skill for a situation
- Fix a run that went wrong
- Make nstack my own

Check the state that changes the answer, and mention it only when it does:

- nstack works without setup: every delegated role has a built-in default model. Run `/nstack:setup-nstack` to inspect or change the effective choices; don't infer that setup is missing from defaults alone.
- No `verify-*` skill or other app harness in the project means agents have no scripted way to drive the app. Mention `/nstack:create-verification-skill` when the question is about proving a change works.
- A configured model is not proof that the client used it. Route dispatch questions to [`setup-nstack`](../setup-nstack/SKILL.md).

When model choices matter, ask whether the user wants to pick a model for each role and a reasoning effort now. It matters when the user is new, the question is about setup or cost, or the answer depends on which models run. Ask at most once per chat. If the need is also unclear, resolve it first, then ask the setup question. Offer two choices:

- Now: give them `/nstack:setup-nstack` to type, and answer their question too.
- Later: answer their question, and add one line saying every role keeps its current model until they run `/nstack:setup-nstack`.

## Get set up

1. Run `copilot plugin marketplace add nilpath/nilpath-marketplace`, then `copilot plugin install nstack@nilpath-marketplace`.
2. Optionally run [`/nstack:setup-nstack`](../setup-nstack/SKILL.md). It reviews the model and effort for each role, previews overrides before applying them, and checks dispatch. Model changes apply to the next launch; panel seat counts apply to new sessions.
3. Start a real task with `/nstack:nstack-flow`, a goal, and a check that can pass or fail.

Installing does not start a workflow. `nstack-flow`, `setup-nstack`, and this help skill require explicit invocation. The [README](../../README.md) has the details. Offer to word their first prompt with them, per [`references/prompting.md`](references/prompting.md).

If cost is the worry, say where the tokens go and how to spend fewer. nstack spends extra tokens on subagents and review panels. Rerun `/nstack:setup-nstack` and pick cheaper models or lower supported effort. A role set to `inherit` runs on the chat's model. A shorter panel list runs fewer subagents, one for each entry, within the supported seat limits. Save `/nstack:nstack-flow` for work that needs rigor.

nstack supports Claude Code, GitHub Copilot CLI, and Codex. Native Copilot use inside VS Code is unsupported; Copilot CLI in a VS Code terminal remains CLI usage. It needs Python 3.11+ for its model hook and setup. Read the README's requirements and limits before diagnosing a failed launch.

Visual plans and recaps also need Node.js 20+ for their local MDX viewer. Session start ensures the viewer without installing packages. A viewer warning does not disable model routing. Both visual skills have an explicit startup fallback.

Copilot CLI namespaces these commands under `nstack:`. In non-interactive prompt mode (`copilot -p`), slash commands are not expanded into skills, so start the workflow and setup interactively. Keep the manual-only flag even if a client version fails to invoke a skill; do not remove it as a workaround.

## Start a task with `/nstack:nstack-flow`

`/nstack:nstack-flow` matches the task to a playbook, copies the playbook's steps into the todo list, and runs the other skills as the steps need them. A step it skips stays in the list with a one-line reason. A good prompt states the goal and how to tell it's done. It doesn't list skills, because a hand-written sequence tends to drop or reorder steps the playbook would keep. Read [`references/prompting.md`](references/prompting.md) before you help word one.

Start each new task with `/nstack:nstack-flow`; nstack does not provide Cursor's persistent Custom Mode. Mid-chat, "new task" makes the coordinator match a fresh playbook. `nstack-flow` already uses `nstack-agent` for the subagents its playbook steps spawn. For subagents of your own, follow its Subagents section, including the role tag, rather than copying Cursor's launch syntax.

## Pick a skill

The default answer is `/nstack:nstack-flow`, which runs most of the others when its steps need them. Name a skill directly when the user wants more or less of something than the playbook gives. Read the skill before you recommend it, and give one example prompt.

| The user wants to | Skill |
|---|---|
| Do any non-trivial task with rigor | [`/nstack:nstack-flow`](../nstack-flow/SKILL.md) |
| Know how code works now, or where new code should live | [`/nstack:how`](../how/SKILL.md) |
| Know why code is shaped this way, or where a number came from | [`/nstack:why`](../why/SKILL.md) |
| Settle types and module shape before code that crosses a function boundary | [`/nstack:architect`](../architect/SKILL.md) |
| Get several attempts at one brief, merged into the best one | [`/nstack:candidate-graft`](../candidate-graft/SKILL.md) |
| Run parallel checks over slices, or race workers | [`/nstack:swarm`](../swarm/SKILL.md) |
| Have different models review a diff and try to break it | [`/nstack:review-panel`](../review-panel/SKILL.md) |
| Review proposed work visually, including proposed APIs | [`/nstack:visual-plan`](../visual-plan/SKILL.md) |
| Inspect actual changes visually, with evidence and API comparisons | [`/nstack:visual-recap`](../visual-recap/SKILL.md) |
| Fix a bug test-first when a cheap local test exists | [`/nstack:tdd`](../tdd/SKILL.md) |
| Apply TypeScript rules to `.ts` or `.tsx` work | [`/nstack:typescript-best-practices`](../typescript-best-practices/SKILL.md) |
| Apply repository-first Python guidance, including contract docstrings | [`/nstack:python-best-practices`](../python-best-practices/SKILL.md) |
| Strip comments before review, using a reviewer that didn't write them | [`/nstack:no-comments`](../no-comments/SKILL.md) |
| Remove AI-generated code slop | [`/nstack:deslop`](../deslop/SKILL.md) |
| Clean AI tells out of prose | [`/nstack:unslop`](../unslop/SKILL.md) |
| Write docs, an RFC, a README, a PR description, or a commit message to a standard | [`/nstack:technical-writing`](../technical-writing/SKILL.md) |
| Give agents a scripted way to drive the app and prove behavior | [`/nstack:create-verification-skill`](../create-verification-skill/SKILL.md) |
| Bring a verification skill and its feature map back in line with the app | [`/nstack:maintain-verification-skill`](../maintain-verification-skill/SKILL.md) |
| Drive a CLI or TUI on its real surface | [`/nstack:control-cli`](../control-cli/SKILL.md) |
| Drive a browser or Electron app on its real surface | [`/nstack:control-ui`](../control-ui/SKILL.md) |
| Vet a performance number before reporting or acting on it | [`/nstack:benchmark-checklist`](../benchmark-checklist/SKILL.md) |
| Run a large or cross-cutting change, or one to review after stepping away | [`/nstack:figure-it-out`](../figure-it-out/SKILL.md) |
| Keep a decision log during a run, and review it afterward | [`/nstack:show-me-your-work`](../show-me-your-work/SKILL.md) |
| Pick a model for each role and a reasoning effort | [`/nstack:setup-nstack`](../setup-nstack/SKILL.md) |
| Find their way around nstack | `/nstack:nstack-help` |

If a skill directory next to this one is missing from the table, read its frontmatter and route by its description. The `principle-*` directories are covered under principles below.

Close calls:

- `/nstack:how` explains what the code does. `/nstack:why` explains the reasons.
- `/nstack:candidate-graft` gives every worker the same brief and merges the best parts. `/nstack:swarm` splits work into slices or a race and returns one report.
- `/nstack:architect` implements right after it settles the design. Add "with checkpoint" to review the design before it writes code.
- `/nstack:review-panel` reviews the diff. It does not apply fixes.
- `/nstack:figure-it-out` designs one rigorous run when none of the bundled playbooks fits.

Not in nstack:

- pstack-only skills and playbooks are not installed by nstack. Don't recommend an upstream command as if it shipped here.
- Cursor's Custom Modes and `/loop` are not portable nstack features.
- PR babysitting, marking ready, merging, and auto-merge are outside nstack. Feature and bug-fix runs stop at a draft pull request.

## Playbooks and principles

Playbooks are step lists inside `nstack-flow`, not skills, so they have no separate command. Inside `nstack-flow`, describing the task picks one:

- New or changed behavior runs [Feature](../nstack-flow/playbooks/feature.md).
- A reported defect runs [Bug fix](../nstack-flow/playbooks/bug-fix.md).
- A read-only question runs [Investigation](../nstack-flow/playbooks/investigation.md), ending in a cited answer without edits or a pull request.

The Playbooks section of [`nstack-flow`](../nstack-flow/SKILL.md) lists every bundled playbook and when it applies. Large, cross-cutting, unattended, or otherwise unmatched work routes to `figure-it-out` for a bespoke playbook. [Draft delivery](../nstack-flow/references/delivery.md) covers opening the pull request, not landing it.

nstack has no standalone planning skill. For a design question, `/nstack:architect` settles the shape in code first; ask for a checkpoint when the user wants to approve it before implementation.

Principles are one-rule skills that `nstack-flow` reads and cites in its replies. The user rarely invokes one. They steer with the names instead, as in "apply prove it works. show me the real output." Typing `/nstack:principle-<name>` still loads one on demand. The Principles section of `nstack-flow` lists all 24.

## Fix a run that went wrong

| Symptom | Fix |
|---|---|
| The workflow stopped applying after a few turns | Start each new task with `/nstack:nstack-flow`; there is no portable persistent mode. |
| A question got treated as the next step of the last task | Say "new task", or say the turn doesn't need the workflow. |
| A new model choice had no effect | Overrides apply to the next launch; panel seat counts need a new session. Run `/nstack:setup-nstack` to inspect state and check dispatch. |
| Runs cost more than expected | See the cost paragraph under Get set up. |
| A skill didn't load on its own | Explicit-only skills load when the user invokes them or the workflow reads their instructions. It doesn't run every skill. |
| A delegate reports that the hook did not run, or rejects a model | Stop that delegation, show the error, and run `/nstack:setup-nstack`. Never silently fall back to another model or do the delegated work inline. |
| Parallel agents overwrote each other | Give each writing agent its own worktree or disjoint file ownership. |
| An unattended run moved but finished nothing | Give it a check that can pass or fail, not a duration, and route the run through `figure-it-out`. |
| The reply claims success from a green build | Ask for the real command, flow, stored value, or profile. That's the prove-it-works principle. |
| The local visual viewer did not start | Read either visual skill's shared viewer workflow. Resolve its installed helper, run `ensure`, and report its error and repair. Do not expose the server publicly or install packages from a hook. |

For a run that drifts, [`references/prompting.md`](references/prompting.md) has one-line steers.

## Make nstack my own

- `/nstack:setup-nstack` reviews and overrides model choices per role without changing the skills.
- `/nstack:nstack-flow write a skill for <workflow>` can use `figure-it-out` when no bundled playbook fits. Keep the change in the repository's authored sources, not an installed or generated copy.
- Fix a misbehaving skill in its own PR, not inside the feature work where it went wrong.

## Reply

Lead with the answer. Give at most one example prompt in a code block, adapted from [`references/recipes.md`](references/recipes.md) when one fits, then the link to that file. Keep it short unless the user asked for the whole map.

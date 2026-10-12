---
name: create-verification-skill
description: Generates a project-local skill for driving the real app and proving user-facing behavior on any language, framework, or platform. Invoke explicitly to create a verification skill, make a control skill for a repo, or establish repeatable UI, CLI, or service verification.
---

# Create a verification skill

Generate a project-local skill at `.agents/skills/verify-<app>/` that launches the real app, exercises features as a user would, and captures evidence. Write it for the next agent: a reader arriving cold, mid-task, with no prior knowledge of the app.

Invoke explicitly with `$create-verification-skill`. Do not load this authoring workflow automatically.

## 1. Select the project and check for an existing skill

Resolve the intended project root before writing anything. The output path is relative to that project, not this installed plugin. If the workspace contains several possible projects and the request does not identify one, use a direct chat question to the user (wait for their reply before continuing) to select it.

Check `.claude/skills/`, `.github/skills/`, and `.agents/skills/` in that project for an existing verification skill: a `SKILL.md` with launch/drive instructions and a feature map. Names usually start with `verify-`, but names alone are not sufficient. Resolve symlinks and deduplicate paths to the same directory.

If a matching skill exists, stop and point to the `maintain-verification-skill` skill. If distinct candidates or an occupied output path make the target ambiguous, use a direct chat question to the user (wait for their reply before continuing) to resolve it. Never silently overwrite a skill or create a competing copy for another harness.

Create only the active harness's project-local skill. Do not install synchronized copies or change the user's global skill configuration.

## 2. Interview the repo, not the user

Answer these from code and documentation; ask only what cannot be observed:

- **Surface:** what does a user touch: web UI, CLI/TUI, desktop app, API, mobile app, or library? Pick the primary surface and note others.
- **Run:** how does it start locally? Prefer the repo's documented dev command, package scripts, Makefile, or quickstart. Record ports, environment variables, authentication, migrations, and seed data.
- **Drive:** how can an agent interact programmatically? Prefer existing Playwright/Cypress tests, expect scripts, PTY helpers, HTTP endpoints, or debug ports. Only then choose a generic browser/CDP, terminal/PTY, or HTTP recipe. Use capabilities available in this environment, not an assumed editor-specific tool.
- **Observe:** what evidence is available: screenshots, terminal transcripts, response bodies, logs, exit codes, or stored state?
- **Isolate:** can instances run side by side with separate ports, data directories, and profiles? If not, say so. Refusing to double-drive a shared instance is better than corrupting the user's session.

If the checkout cannot build or start, fix the prerequisite within the user's authorized scope or report the blocker precisely before generating. Do not teach steps against a broken base. An irrelevant missing asset may be created as clearly identified verification scaffolding and removed during cleanup; do not disguise a product fix as scaffolding.

## 3. Generate the skill

Write `.agents/skills/verify-<app>/SKILL.md` with YAML frontmatter containing `name: verify-<app>` and a description naming the app, surface, and when to verify it. Replace `<app>` with a valid lowercase, hyphenated name matching the directory. Normal verification skills remain eligible for automatic discovery; do not copy this authoring workflow's manual-only policy unless requested.

Ground every instruction in the repository. Leave no placeholders or example commands in the generated deliverable. Include:

- **Launch:** the exact command and readiness condition. Reach a usable state from an empty data directory, including migrations and seed data. Ready means usable, not merely that a port answers: database health can pass before initialization finishes. Include teardown. For short-lived CLI/TUI programs, build or install dependencies once, then start each drive in its own isolated PTY or terminal session.
- **Doctor:** one read-only check answering "is this instance worth driving?" Check the process, expected build/version, owned port, and authentication as appropriate. Run it before driving and whenever something looks wrong.
- **Drive:** the harness recipe with actual selectors, commands, and routes. Prefer stable handles such as accessible names, data attributes, prompts, and route paths over coordinates or tab order.
- **Evidence:** name a durable artifact location. Exercise the real user path, not internal setters or test-only endpoints. Capture the action and resulting state, not only a final screen. Verify side effects such as files, rows, or messages alongside visible results. Mock only at an existing production boundary. For a dry-run or test mode, observe what it actually skips through files, network activity, or git refs; its name is not proof that it has no side effects.
- **Cleanup:** stop only instances the run created, using recorded process IDs or owned session handles, never process names. Remove owned scratch state, not evidence. Proof artifacts must survive teardown at the named location. Do not tear down a shared instance owned by the user.
- **Helpers:** make supplied scripts executable and show their exact invocation in the skill body. Use paths relative to the generated skill's own resources, not paths into this authoring plugin. A reader must not have to reverse-engineer a helper.

## 4. Seed the feature map

Create `.agents/skills/verify-<app>/features/README.md` and one file per identifiable user-facing feature, aiming for the top 3-5 from routes, commands, menus, or docs.

Follow the structure in the [feature-map example](./references/feature-map-example/README.md), [create-note journey](./references/feature-map-example/create-note.md), and [search journey](./references/feature-map-example/search.md). These are illustrative Notes app recipes, not runnable commands for the target project. Replace their app details and commands with observed facts.

The index links to every feature file. Each file starts with a title and user-visible description, then these four H2 sections in order:

1. `Sub-features`
2. `How to get to it (user POV)`
3. `Driving it with <harness>` (replace `<harness>` with the actual app-driving harness)
4. `Gotchas`

Describe how to reach the feature, exact driving steps, preconditions, and observable success. If seed data lacks a required precondition, report the journey's failure and record the reason in `Gotchas`. Never weaken the journey to make it pass. The feature map is the maintained verification source: proving one convenient entry point is incomplete when it lists others.

## 5. Prove the generated skill

Follow the generated instructions end to end: launch, doctor, drive one mapped feature, capture evidence, and clean up. One feature is enough for this initial proof; later maintenance covers the whole map.

After cleanup, confirm the evidence still exists at the named location. Fix failures and rerun the generated cleanup after every failed iteration so attempts do not strand processes, ports, or scratch state. Never claim an unexecuted skill is complete: it is a draft.

If proof used a stand-in such as a container instead of a fresh VM or a local stack instead of a remote target, list every setup step the stand-in supplied that the real target will not. Those steps remain unverified until exercised on the real target.

## 6. Hand over and maintain

Report the generated location, feature map, feature actually proved, artifact location, and any unverified prerequisites. Do not commit, push, or open a PR as part of generation unless explicitly requested. Point to the `maintain-verification-skill` skill for upkeep. Suggest a maintenance cadence only if asked.

## Attribution

Adapted from [pstack's create-verification-skill](https://github.com/cursor/plugins/blob/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack/skills/create-verification-skill/SKILL.md), copyright (c) 2026 Lauren Tan, under the [MIT license](./LICENSE).

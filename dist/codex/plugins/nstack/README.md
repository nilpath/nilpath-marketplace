# nstack

A portable engineering backbone for Claude Code, GitHub Copilot CLI, and Codex, adapted from [pstack](https://github.com/cursor/plugins/tree/dbf49813a39c1a5389c5e28cb8e4c1c2379e2454/pstack).

Version 0.1.0 expands the coordinator to fifteen native playbooks, including bounded PR monitoring, experiments, dependency-aware execution, recovery, and exact-target cleanup. Product changes still require a proposal and user approval unless an explicit scoped grant covers autonomous implementation.

The explicit coordinator selects a method from its [complete playbook index](skills/nstack-flow/SKILL.md#playbooks), grounds the work, obtains needed authority, delegates bounded units, and verifies actual results. Product delivery stays draft-only. Planning, experiments, monitoring and recovery have their own honest stopping points.

## Skills

| Skill | Invocation | Purpose |
| --- | --- | --- |
| nstack-flow | Explicit only | Coordinator with native engineering, experiment, PR, planning, orchestration, recovery, and cleanup methods; shared authority and evidence owners |
| nstack-help | Explicit only | pstack's poteto-help adapted to nstack: setup, skill and playbook selection, troubleshooting, and copyable prompts |
| setup-nstack | Explicit only (optional) | Reviews and overrides the model and effort per delegated role, and checks that the client runs them |
| how | Automatic or explicit | Source-grounded explanation of how a subsystem works (explorers plus an explainer) |
| why | Automatic or explicit | Evidence-tiered history of why code is the way it is (investigators plus a synthesizer) |
| architect | Automatic or explicit | Usage-first design: grounds the problem, sketches at least two structurally distinct designs, synthesizes one |
| candidate-graft | Automatic or explicit | pstack's arena: independent candidates, a blind cross-judge, a chosen base, and grafted strengths from the others |
| swarm | Automatic or explicit | Bounded parallel coverage or races with a declared completion or selection rule |
| review-panel | Automatic or explicit | pstack's interrogate: independent adversarial reviewers plus a lead judgment (Act on, Consider, Noted, Dismissed) |
| 24 `principle-*` skills | Explicit only | pstack's principles, indexed in nstack-flow's Principles section and read in full when applied |
| unslop, technical-writing, no-comments, deslop | Explicit only | Prose and code cleanup triggered by nstack-flow's non-negotiables |
| control-cli, control-ui, benchmark-checklist, tdd | Explicit only | Driving real surfaces, vetting measurements, failing-test-first bug fixes |
| show-me-your-work, figure-it-out, typescript-best-practices | Explicit only | Decision trails, bespoke playbooks when none fits, TypeScript patterns |
| python-best-practices | Explicit only | Python editing/review with Google as the fallback baseline, repository-supported tooling first, contract docstrings, typing, resources, and focused tests |
| create-verification-skill, maintain-verification-skill | Explicit only | Generate a project-local `verify-<app>` skill with a feature map, and keep it in line with the app through a source pass, one live pass, and at most one draft pull request |

"Explicit only" skills stay out of the client's automatic skill catalog. nstack-flow and the agents read them directly from `../<name>/SKILL.md`.

`python-best-practices` is independently invoked: `/nstack:python-best-practices` in Claude Code or Copilot CLI, or `$python-best-practices` in Codex. It adds no prerequisite skill or tool dependency and preserves established repository documentation styles. `no-comments` and Comment Sicko preserve Python documentation contracts and semantic directives, audit suppressions by actual rule/diagnostic, and leave unknown classifications unresolved. Correctness suppressions require a root-cause fix before removal.

## Agents

- **nstack-agent**: the delegate for roles that may write or call tools: implementation tiers (`implementer`, `implementer-hard`, `judgment`), swarm workers, candidate and design runners, and `why` investigators. An explicitly assigned program coordinator can launch bounded workers or child coordinators using inherited authority and configured roles. Ordinary workers do not spawn; publication follows explicitly assigned authority and user limits.
- **nstack-reader**: the read-only delegate (read and search tools only) for `how` explorers and explainers, the candidate-graft judge, and review-panel reviewers.

- **comment-sicko**: pstack's comment hunter, extended for Python docstrings and semantic directives, spawned by `no-comments`. It runs on the session's model.

nstack-agent and nstack-reader have no model. nstack's model hook sets the model per launch.

Every nstack-agent role reads the full nstack-flow skill and its inline Principles index before work. It uses the parent's absolute path or the active plugin path supplied by the verified hook, not a different installed version selected by catalog search. Missing hook/model dispatch still stops the delegate. Read-only roles retain their existing nstack-reader contract, and background preference stays in the launch policy rather than Cursor's agent-only `is_background` field.

## Playbooks

The [coordinator's method index](skills/nstack-flow/SKILL.md#playbooks) is the single complete inventory. Playbooks are not separately invocable skills. Explicit intent selects the method before effort size or stepping away; unmatched work uses figure-it-out.

Babysit can check or watch CI/reviews and execute covering-approved fixes. Observation does not waive sign-off or user action limits. Recurring work requires the host's real scheduling capability, not an assumed persistent chat. The coordinator never marks ready, merges, or enables auto-merge. User no-commit, no-push, no-PR, and local-only limits still apply.

[Opening a PR](skills/nstack-flow/playbooks/opening-a-pr.md) owns publication instructions. It preserves upstream's built-in PR-tool preference; the existing draft publisher is used only for the GitHub CLI publication path. No separate delivery guide or duplicate PR-body format is maintained.

The copied playbooks use pstack's existing orchestration, PR-watch, plan-checking and worktree-audit helpers and dependency files. No separate Python/SQLite accounting framework is added. Explicitly assigned program coordinators may launch child coordinators using inherited scope and existing configured roles. Copies retain upstream content except for the operator-approved substitutions below.

Bundled rule reads use `gh api` against this repository's `main` and the rendered tree matching the current harness. Project-code baselines still use the project's trunk. A missing rule read stops the workflow; it does not silently substitute an installed or working-copy version. These trunk rules can be newer than installed helpers.

Claude uses its available native `/loop`; other hosts require an actually exposed recurring-automation capability and stop if it is absent. No new scheduling service is added. Workers may use isolated local worktrees instead of mandatory Cursor cloud placement. Native worker/session evidence replaces Cursor-only transcript paths; unavailable evidence remains unverified. Independent configured models/seats are used for judges/verifiers, with same-family limits reported rather than invented model diversity.

Pause and pickup preserve work within the user's commit limits and recover existing authority. Cleanup retains the upstream audit/prune sequence, but exact destructive targets and possible data loss require explicit approval. Host-managed worktrees use supported lifecycle tools; current/main workspaces are protected. The upstream audit's Cursor-derived chat information is advisory, not proof of a nstack session's current activity.

## Implementation sign-off

An ordinary code-changing request to `nstack-flow` now ends its design turn with a proposal. Review the intended behavior, actual edit locations, proposed shape, exclusions, and checks before approving implementation. A same-function bug fix gets a short cause, edit, and check proposal without mandatory architecture fan-out. Approval covers execution and corrective review fixes within that scope, not permission for every edit.

The same boundary applies to `figure-it-out`, standalone `architect`, and code-producing `candidate-graft`. A nested architect returns design only to the coordinator, even under an outer autonomy waiver. The coordinator asks once and owns implementation. Read-only Investigation stays read-only without an approval ceremony.

To waive the ordinary checkpoint for a scope, explicitly grant it, for example, "implement this migration autonomously" or "skip sign-off for this fix." An ordinary request to implement, tool permission approval, silence, or "going to bed" alone is not a waiver. Named stops and plan-only requests still stop. Questions and requested revisions do not authorize implementation.

Before authority exists, preparation can read source, run safe existing checks, and write isolated scratch designs or diagnostic-only reproductions. It cannot edit product files, create product scaffolds or shipping tests, launch implementing delegates, or produce production candidates in another worktree. Product instrumentation also needs covering approval before the edit, even if it would later be reverted.

Material scope changes need new approval unless a grant covers them. On continuation, the coordinator recovers the matching proposal and attributable user approval or grant. Missing or ambiguous authority, or no reply channel, means stop. Irreversible-action pauses and delivery limits remain independent.

The [sign-off contract](skills/nstack-flow/references/sign-off.md) owns these rules. This is an instruction-level boundary, not technical write enforcement. Rendered-document tests check packaging and handoffs, not runtime stopping or reduced rework.

## Model configuration

nstack works without setup: every delegated role has a built-in default model, and effort where the client supports it.

- Every nstack launch carries a role tag such as `[nstack role=review-panel-reviewer seat=2]`. That tag is all the skills know about model selection.
- A plugin hook runs before every subagent launch. For a tagged launch it writes the role's model and effort into the launch call, routes read-only roles to `nstack-reader`, and tells the subagent which instructions to read first. Untagged launches pass through untouched.
- At session start, the hook adds one context line listing each panel role's seats and models, so panel skills know how many seats to launch.
- The hook's script (`nstack_config.py`) ships in the plugin's hooks directory, next to `hooks.json`.
- Overrides are stored per user in `~/.nstack/models.json`, per client (`claude`, `copilot`, `codex`). Run `setup-nstack` to change them; changes apply to the next launch, with no restart.
- A configured model is not proof that the client used it. `setup-nstack` records a dispatch check only when the client itself shows which model ran.

| Client | Model per launch | Effort per launch | Built-in defaults (fast / strong / panel) |
| --- | --- | --- | --- |
| Claude Code | Aliases only: `sonnet`, `opus`, `haiku`, `fable` | Not supported | `sonnet` / `opus` / `opus` + `sonnet` |
| Copilot CLI | Model ids, such as `claude-opus-5.5` | `low` to `max` | `claude-sonnet-5` medium / `claude-opus-5.5` high / `claude-opus-5.5` + `gpt-6.1-sol` high |
| Codex | Model ids, such as `gpt-5.6-sol` | `minimal` to `ultra` | `gpt-5.6-luna` medium / `gpt-5.6-sol` high / `gpt-5.6-sol` + `gpt-5.6-terra` high |

Defaults are suggestions: an account may not have every model. A model the client rejects fails the launch visibly; nstack never falls back to another model.

## Requirements and limits

- Python 3.11+ for the model hook and `setup-nstack`.
- Bun for the copied orchestration and PR-watch tools, Node.js for the plan checker, and the helpers' original dependency files. The upstream bootstrap may install dependencies before its first CLI invocation.
- **Codex:** trust nstack's plugin hook once with `/hooks`. Until then, nstack agents reply that the hook did not run, and delegation stops.
- Read access to the plugin's install directory: skills and subagents read their reference files there. Interactive sessions ask for approval; non-interactive runs must pre-approve it (for example, Copilot CLI's `--add-dir`).
- The model hook is verified for Copilot CLI and Claude Code plugins, and with the same hook command in Codex. Codex loading it from an installed plugin is not yet verified. Native Copilot use inside VS Code is unsupported. Copilot CLI in a VS Code terminal remains CLI usage.
- Skill approvals do not control plugin hooks. Broad Claude shell grants for orchestration stay unchanged. Copilot skill approval emission is disabled, so those declarations do not become blanket CLI approvals. `show-me-your-work` preapproves only its rooted logger on Claude. Resolve its installed absolute path and use ordinary approval on Copilot CLI and Codex.
- If `python3` is missing or older than 3.11, the hook steps aside rather than blocking other tools; nstack agents then report that the hook did not run.
- `git` and an authenticated `gh` CLI for draft pull requests.
- Copilot CLI namespaces plugin skill commands (`/nstack:how`, `/nstack:nstack-flow`), but the skill names the model sees (`how`, `why`, `swarm`, and the others) can still collide with skills from other plugins. In Copilot CLI's non-interactive prompt mode (`-p`), slash commands are not expanded into skills, so start `nstack-flow` and `setup-nstack` interactively.
- Delegation quality depends on the session model following the skill's procedure. In testing, a small session model (`gpt-5-mini`) loaded an nstack skill and then answered inline without delegating; use a capable model for the coordinating session.
- Read-only roles run on `nstack-reader`, whose tools are limited to reading and searching (and a read-only sandbox in Codex). The `why` roles run on `nstack-agent` with full tool access for MCP evidence sources; their no-write rule is an instruction only.

## Attribution

The Python best-practices skill is an original summary linking to the Google Python Style Guide, not copied guide text. Its repository-first guidance and the Python-aware cleanup policy are nstack additions.

`nstack-help` and its prompting and recipe references are adapted from [pstack's poteto-help](https://github.com/cursor/plugins/tree/8b3326d99fd4b993cb33a24dad8af03175c642c5/pstack/skills/poteto-help) at commit `8b3326d99fd4b993cb33a24dad8af03175c642c5` (pstack 0.15.30), under the same Lauren Tan MIT License below. Wording is retained where it applies; commands, setup, public source links, and the inventory match nstack's three clients and bundled playbooks. Unsupported pstack-only workflows are not offered.

The twelve added procedures, bot-triage reference and supporting scripts are copied from [poteto-mode](https://github.com/cursor/plugins/tree/8b3326d99fd4b993cb33a24dad8af03175c642c5/pstack/skills/poteto-mode) at that same pin (pstack 0.15.30, MIT copyright Lauren Tan 2026). Keep upstream content verbatim except for operator-approved mechanical substitutions and narrowly approved nstack constraints. Older component provenance below remains unchanged.

nstack adapts workflows, prompts, and principles from pstack by Lauren Tan (poteto), and the deslop, control-cli, and control-ui skills from Cursor's cursor-team-kit. Both are published in [cursor/plugins](https://github.com/cursor/plugins) at commit `dbf49813a39c1a5389c5e28cb8e4c1c2379e2454` (pstack 0.15.23) under the MIT License. Most skill text is copied verbatim; nstack replaces Cursor-specific mechanics (the Task tool, model rule files, cloud workers) with its own launch tags and model hook. nstack is not affiliated with or endorsed by the pstack author or Cursor.

```text
MIT License

Copyright (c) 2026 Lauren Tan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

```text
MIT License

Copyright (c) 2026 Cursor

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

> Generated from this repo's `src/plugins/nstack/` sources — edit there, not in `dist/`.

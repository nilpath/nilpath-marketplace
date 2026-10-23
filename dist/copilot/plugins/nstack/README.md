# nstack

A portable engineering backbone for Claude Code, GitHub Copilot CLI, and Codex, adapted from [pstack](https://github.com/cursor/plugins/tree/dbf49813a39c1a5389c5e28cb8e4c1c2379e2454/pstack).

An explicit coordinator picks a playbook (feature, bug fix, or investigation), grounds the work in the existing code and its history, compares alternative designs, delegates bounded implementation, proves the result against the real artifact, has it reviewed independently, and ends a code change as a draft pull request.

## Skills

| Skill | Invocation | Purpose |
| --- | --- | --- |
| nstack-flow | Explicit only | Coordinator in poteto-mode's shape: non-negotiables, principles, autonomy, subagents, reply and comment rules, and the feature, bug-fix, and investigation playbooks |
| nstack-help | Explicit only | pstack's poteto-help adapted to nstack: setup, skill and playbook selection, troubleshooting, and copyable prompts |
| setup-nstack | Explicit only (optional) | Reviews and overrides the model and effort per delegated role, and checks that the client runs them |
| how | Automatic or explicit | Source-grounded explanation of how a subsystem works (explorers plus an explainer) |
| why | Automatic or explicit | Evidence-tiered history of why code is the way it is (investigators plus a synthesizer) |
| architect | Automatic or explicit | Usage-first design: grounds the problem, sketches at least two structurally distinct designs, synthesizes one |
| candidate-graft | Automatic or explicit | pstack's arena: independent candidates, a blind cross-judge, a chosen base, and grafted strengths from the others |
| swarm | Automatic or explicit | Bounded parallel coverage or races with a declared completion or selection rule |
| review-panel | Automatic or explicit | pstack's interrogate: independent adversarial reviewers plus a lead judgment (Act on, Consider, Noted, Dismissed) |
| visual-plan | Automatic or explicit | Proposed work as a rich local MDX document with diagrams, API contracts, wireframes, and review questions |
| visual-recap | Automatic or explicit | Actual changes as a rich local MDX document with evidence, comparisons, API contracts, and honest inference labels |
| 24 `principle-*` skills | Explicit only | pstack's principles, indexed in nstack-flow's Principles section and read in full when applied |
| unslop, technical-writing, no-comments, deslop | Explicit only | Prose and code cleanup triggered by nstack-flow's non-negotiables |
| control-cli, control-ui, benchmark-checklist, tdd | Explicit only | Driving real surfaces, vetting measurements, failing-test-first bug fixes |
| show-me-your-work, figure-it-out, typescript-best-practices | Explicit only | Decision trails, bespoke playbooks when none fits, TypeScript patterns |
| python-best-practices | Explicit only | Python editing/review with Google as the fallback baseline, repository-supported tooling first, contract docstrings, typing, resources, and focused tests |
| create-verification-skill, maintain-verification-skill | Explicit only | Generate a project-local `verify-<app>` skill with a feature map, and keep it in line with the app through a source pass, one live pass, and at most one draft pull request |

"Explicit only" skills stay out of the client's automatic skill catalog. nstack-flow and the agents read them directly from `../<name>/SKILL.md`.

`python-best-practices` is independently invoked: `/nstack:python-best-practices` in Claude Code or Copilot CLI, or `$python-best-practices` in Codex. It adds no prerequisite skill or tool dependency and preserves established repository documentation styles. `no-comments` and Comment Sicko preserve Python documentation contracts and semantic directives, audit suppressions by actual rule/diagnostic, and leave unknown classifications unresolved. Correctness suppressions require a root-cause fix before removal.

## Agents

- **nstack-agent**: the delegate for roles that may write or call tools: implementation tiers (`implementer`, `implementer-hard`, `judgment`), swarm workers, candidate and design runners, and `why` investigators. Never runs a playbook, spawns subagents, commits, or publishes on its own.
- **nstack-reader**: the read-only delegate (read and search tools only) for `how` explorers and explainers, the candidate-graft judge, and review-panel reviewers.

- **comment-sicko**: pstack's comment hunter, extended for Python docstrings and semantic directives, spawned by `no-comments`. It runs on the session's model.

nstack-agent and nstack-reader have no model. nstack's model hook sets the model per launch.

## Playbooks

| Playbook | Ends with |
| --- | --- |
| Feature | Verified, independently reviewed change published as a **draft** pull request |
| Bug fix | Reproduced-then-fixed change, same proof before and after, published as a **draft** pull request |
| Investigation | A cited answer or recommendation. No edits, no pull request |

The coordinator continues from design into implementation unless you ask for a checkpoint. It never marks a pull request ready, merges, enables auto-merge, or monitors CI.

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

## Visual review documents

`visual-plan` explains proposed work. `visual-recap` explains actual changes and distinguishes implemented, inferred, contextual, and proposed follow-up content. They reuse architect outputs and existing decision trails rather than adding another planning engine.

Both skills author `.mdx` files and publish through one bundled local viewer. The viewer supports diagrams, annotated code, file maps, before-and-after comparisons, decisions, review questions, wireframes, and UI state sequences. API contracts are first-class blocks. They display HTTP method and path or non-HTTP signatures, authentication, parameters, expandable schemas, request and response examples, errors, and contract comparisons. API blocks never send requests or collect credentials.

The MDX compiler uses a standard AST parser and an allowlisted component vocabulary. Rich blocks carry literal attributes and fenced JSON data. Imports, exports, JavaScript expressions, raw HTML, and unknown components are rejected. The browser renders data rather than executing MDX. Graph diagrams use nodes and edges, not Mermaid source. The `components` command and bundled `all-components.mdx` are the authoring reference.

The session-start hook starts or reconnects to the viewer. It preserves model context and reports viewer failures as warnings. It needs Node.js 20+ on `PATH`, but no runtime `npm install`. V1 viewer hosting requires macOS or Linux with POSIX private-directory permissions. Native Windows hosting is unsupported; use WSL or a Linux host. This viewer limit does not change the other nstack skills or model hook. Missing Node does not stop model configuration. Set `NSTACK_VIEWER=off` to disable hook startup.

The skills resolve the installed helper and use the same fallback when hooks do not run:

```bash
node "<installed-viewer>/viewer.mjs" ensure
node "<installed-viewer>/viewer.mjs" components
node "<installed-viewer>/viewer.mjs" check "/absolute/path/review.mdx"
node "<installed-viewer>/viewer.mjs" open "/absolute/path/review.mdx"
node "<installed-viewer>/viewer.mjs" answers "<document-id>"
node "<installed-viewer>/viewer.mjs" stop
```

`open` returns a private local document URL. Open that complete URL in an ordinary browser on any supported client. The viewer exchanges its access capability for an HttpOnly, SameSite cookie and redirects to a clean address. Unauthenticated local clients cannot read documents or obtain the write token. Treat access URLs as private, and use `open` again to open another browser. In the Copilot app, the existing Browser canvas can display the same URL. A custom SDK canvas adapter is not included. Its guide and scaffold tooling were unavailable during implementation. Browser rendering does not depend on the app.

Canonical MDX belongs in the current session's artifacts or a user-selected repository path. Reuse the original canonical path when continuing a review in another session. Use a stable repository path for a review that must outlive session artifacts. Mutable viewer state belongs under `$NSTACK_HOME/viewer/`, or `~/.nstack/viewer/`. Use stable project-specific document IDs and block IDs. The viewer rejects accidental document-ID reuse from another source path. Source-identity migration is not supported in v1. Saved answers survive reload and server restart, and the CLI can read them without starting a server. A changed question marks its old answer stale instead of treating it as the current choice.

The server binds to `127.0.0.1` on an assigned port and verifies its build identity before reuse. It does not depend on end-hook delivery. Closing a tab or canvas does not stop it. The explicit `stop` command checks the matching viewer's identity. Do not kill processes by name or delete shared runtime state.

The capability protects against unauthenticated local accounts and cross-site browser requests. It is not a sandbox against another process running as your operating-system user, which can read your private runtime files.

Local means the agent's host. A remote agent needs a private forwarded port or tunnel for a browser on your machine. Do not bind the viewer publicly. The server is a single-user local review tool, not a hosted collaboration service.

The installed layouts, compiler, hook adapter, lifecycle, and HTTP boundaries have automated checks. Those checks are not proof that every client discovers and invokes its installed hook. Codex hook discovery and the manual skill-invocation caveats below still apply.

## Requirements and limits

- Python 3.11+ for the model hook and `setup-nstack`.
- Node.js 20+ for visual document publication and the optional session-start viewer. Other nstack skills do not need Node.
- macOS or Linux for viewer hosting in v1. Native Windows needs WSL or another Linux host; the viewer does not pretend POSIX mode bits verify Windows ACLs.
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

The visual workflow idea is inspired by Builder.io's [visual-plan and visual-recap skills](https://github.com/BuilderIO/skills/tree/fecf1ffac18165d165bef520b5c6bd49553c7968/skills) and [Agent Native Plan](https://github.com/BuilderIO/agent-native/tree/main/templates/plan). This viewer and its skill text are an independent implementation. They do not use Builder.io's hosted renderer or vendor its application. Bundled parser dependency notices ship beside the viewer.

The Python best-practices skill is an original summary linking to the Google Python Style Guide, not copied guide text. Its repository-first guidance and the Python-aware cleanup policy are nstack additions.

`nstack-help` and its prompting and recipe references are adapted from [pstack's poteto-help](https://github.com/cursor/plugins/tree/8b3326d99fd4b993cb33a24dad8af03175c642c5/pstack/skills/poteto-help) at commit `8b3326d99fd4b993cb33a24dad8af03175c642c5` (pstack 0.15.30), under the same Lauren Tan MIT License below. Wording is retained where it applies; commands, setup, public source links, and the inventory match nstack's three clients and bundled playbooks. Unsupported pstack-only workflows are not offered.

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

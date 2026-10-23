# engineering-workflow

The research → design → plan → implement → review pipeline: orchestrator skills plus the agents they delegate to, and the engineering principles they apply. Ships with a context7 MCP server for library documentation lookups.

Version: **0.8.2**

## Skills

| Skill | Purpose |
| --- | --- |
| researching | Explicitly invoked: gathers context and produces an approved design.md, then hands off the planning command and stops |
| planning | Explicitly invoked: turns an approved design.md into 2–5 minute TDD tasks in plan.md |
| executing-plan | Executes plan.md: worktree, task delegation, per-task review, PR |
| performing-code-review | Full code review for a branch or GitHub PR |
| engineering-principles | SOLID/DRY/KISS/YAGNI design reference |

## Invocation and handoff

**researching** and **planning** require explicit user invocation; neither is loaded automatically by another skill or agent.

| Client | Start research | Start planning with an approved design |
| --- | --- | --- |
| Claude Code | `/engineering-workflow:researching <topic-or-slug>` | `/engineering-workflow:planning docs/features/<NNN>-<feature-slug>` |
| GitHub Copilot CLI | `/researching <topic-or-slug>` | `/planning docs/features/<NNN>-<feature-slug>` |
| Codex | `$researching <topic-or-slug>` | `$planning docs/features/<NNN>-<feature-slug>` |

Research still clarifies scope, explores the codebase and relevant sources, proposes approaches with trade-offs, and writes the chosen design. The spec is reviewed by an agent and the user, revised as needed, and committed. Research then shows the planning command with the actual feature path and **stops**: it does not invoke planning automatically or start implementation. Run the command yourself when ready to create `plan.md`.

Native invocation policy enforces this boundary: Claude Code and Copilot CLI use `disable-model-invocation: true` in skill frontmatter; Codex uses `policy.allow_implicit_invocation: false` in each skill's `agents/openai.yaml` sidecar. Native Copilot use inside VS Code is unsupported. Copilot skill tool approvals remain disabled independently of this invocation policy.

**Copilot CLI limitation:** explicit invocation with this policy has known upstream issues. [github/copilot-cli#4438](https://github.com/github/copilot-cli/issues/4438) reports skills becoming unreachable (`Skill not found`), while [github/copilot-cli#4637](https://github.com/github/copilot-cli/issues/4637) reports a slash command loading successfully alongside a conflicting lookup error. CLI behavior may therefore vary; explicit-invocation enforcement takes precedence, with no fallback that removes the policy or enables automatic invocation.

## Agents

- **planning**: task-decomposer
- **review**: spec-reviewer, plan-reviewer, code-reviewer
- **research**: api-integration-researcher, architecture-researcher, docs-library-researcher
- **implementation**: code-debugger, coding-task-agent, python-task-agent

## Dependencies

Some skills delegate across plugins — install these alongside:

- **git-tools** — executing-plan uses `git-tools:git-commits` and `git-tools:using-git-worktrees`; performing-code-review uses `git-tools:gh-pr-review`
- **documentation** — executing-plan delegates documentation tasks to `documentation:implementation:doc-writer`

> Generated from this repo's `src/plugins/engineering-workflow/` sources — edit there, not in `dist/`.

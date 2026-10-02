# engineering-workflow

The research → design → plan → implement → review pipeline: orchestrator skills plus the agents they delegate to, and the engineering principles they apply. Ships with a context7 MCP server for library documentation lookups.

## Skills

| Skill | Purpose |
| --- | --- |
| researching | Gathers context and writes design.md before any creative work |
| planning | Turns an approved design.md into 2–5 minute TDD tasks in plan.md |
| executing-plan | Executes plan.md: worktree, task delegation, per-task review, PR |
| performing-code-review | Full code review for a branch or GitHub PR |
| engineering-principles | SOLID/DRY/KISS/YAGNI design reference |

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

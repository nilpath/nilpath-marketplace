# Claude Code Tools

A collection of Agents and Skills for coding with Claude.

## Version

0.5.2

## Components

### Agents (1)

| Agent | Description |
|-------|-------------|
| **code-reviewer** | Expert code reviewer for quality, security, and best practices. Can add line comments to GitHub PRs. |

### Agent Details

**code-reviewer**
- Comprehensive review checklist: code quality, error handling, security, performance, testing, architecture, documentation
- Structured output with file:line references for all issues
- **GitHub PR integration**: Creates pending reviews with line-specific comments
- Proactive invocation after code changes
- Tools: Read, Glob, Grep, Bash (restricted to gh/git via skill)
- Skills: gh-pr-review
- Model: sonnet

### Skills (8)

| Skill | Description |
|-------|-------------|
| **creating-agents** | Expert guidance for designing and implementing Claude Code subagents |
| **create-agent-skills** | Expert guidance for creating, writing, and refining Claude Code Skills |
| **creating-mermaid-diagrams** | Create, edit, and validate Mermaid diagrams (flowcharts, sequence, class, ER, etc.) |
| **gh-pr-review** | GitHub PR review operations: create pending reviews with line comments, submit reviews |
| **gh-address-comments** | Address review/issue comments on the open GitHub PR for the current branch |
| **git-commits** | Git commit best practices and message formatting guidelines |
| **git-stacked-prs** | Stacked (dependent) pull request workflow and management |
| **git-advanced** | Advanced git operations, analysis tools, recovery, and command reference |

### Skill Details

**creating-agents** (~280 lines)
- Comprehensive guide for designing and implementing Claude Code subagents
- Core principles: context preservation, parallelization, specialization
- References: official-spec.md, orchestration-patterns.md, tool-permissions.md, anti-patterns.md
- Workflows: create-read-only-agent.md, create-code-writer-agent.md, create-research-agent.md, audit-existing-agent.md
- Templates: code-reviewer.md, debugger.md, researcher.md, domain-expert.md
- Examples: real-world-agents.md with battle-tested configurations

**create-agent-skills**
- Expert guidance for authoring Claude Code Skills
- References: 10+ reference files covering best practices
- Workflows: Multiple workflow files for skill creation
- Templates: Skill templates for quick starts

**creating-mermaid-diagrams**
- Create, edit, and validate all Mermaid diagram types
- **References**: 12 quick reference files (~50 lines each)
  - Flowchart, Sequence, Class, State, ER, Gantt, Pie, Mindmap, Timeline, Git Graph
  - Styling/themes, common patterns
- **Templates**: 5 starter templates (flowchart, sequence, class, architecture, ER)
- **Workflows**: create-diagram.md, edit-diagram.md, validate-diagram.md
- **Scripts**: `validate-mermaid.sh` - Syntax validation via mermaid-cli
- Progressive disclosure: Links to official Mermaid docs for advanced features

**gh-pr-review**
- GitHub PR review operations via gh CLI
- **Scripts**: 3 automation scripts
  - `pr-info.sh` - Get PR context (number, repo, diff files)
  - `create-review.sh` - Create pending review with line comments
  - `submit-review.sh` - Submit pending review (approve/reject/comment)
- References: api-reference.md with GitHub API details
- Creates PENDING reviews so user can edit before submitting

**gh-address-comments**
- Address review/issue comments on open PR for current branch
- Complements gh-pr-review (creating reviews) with responding to reviews
- **Scripts**: `fetch-comments.sh` - Fetch all PR comments via GitHub GraphQL API
- Workflow: Fetch comments → Summarize actionable items → Apply fixes
- Fetches: conversation comments, reviews, inline review threads (with resolved/outdated state)

**git-commits** (241 lines)
- Commit best practices and conventional commits format
- References: commit-guidelines.md
- Templates: commit-message.txt

**git-stacked-prs** (311 lines)
- Stacked PR creation, management, and troubleshooting
- References: stacked-prs.md
- Workflows: create-stacked-prs.md, update-stack-after-merge.md, recover-from-rebase.md
- Templates: pr-description.md
- **Scripts**: 4 automation scripts (820 lines total)
  - `stack-status.sh` - Display visual tree of stack structure with PR status
  - `stack-backup.sh` - Create and restore backups before risky operations
  - `stack-rebase.sh` - Automate sequential rebasing with safety features
  - `update-pr-targets.sh` - Batch update PR targets after merges

**git-advanced** (350 lines)
- Interactive rebase, cherry-pick, reflog, stash, reset, clean, bisect
- History analysis: blame, search, bisect
- Recovery: lost commits, deleted branches, undo reset
- References: advanced-operations.md, common-commands.md

## Credits

Inspired by:
- [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin)
- [Anthropic Agent Skills Documentation](https://code.claude.com/docs/en/skills)

### Sourced Skills

| Skill | Source |
|-------|--------|
| create-agent-skills | [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) |
| gh-address-comments | [openai/skills](https://github.com/openai/skills/tree/main/skills/.curated/gh-address-comments) |

### Sourced Commands

| Command | Source |
|---------|--------|
| create-agent-skill | [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) |

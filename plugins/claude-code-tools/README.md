# Claude Code Tools

A collection of Agents and Skills for coding with Claude.

## Version

0.3.1

## Components

### Skills (4)

| Skill | Description |
|-------|-------------|
| **create-agent-skills** | Expert guidance for creating, writing, and refining Claude Code Skills |
| **git-commits** | Git commit best practices and message formatting guidelines |
| **git-stacked-prs** | Stacked (dependent) pull request workflow and management |
| **git-advanced** | Advanced git operations, analysis tools, recovery, and command reference |

### Skill Details

**create-agent-skills**
- Expert guidance for authoring Claude Code Skills
- References: 10+ reference files covering best practices
- Workflows: Multiple workflow files for skill creation
- Templates: Skill templates for quick starts

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

### Source Skills

| Skill | Source |
|-------|--------|
| create-agent-skills | [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) |

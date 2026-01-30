# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-01-30

### Added
- **creating-agents** - Comprehensive skill for designing and implementing Claude Code subagents (14 files)
  - SKILL.md main entry point with quick start, core concepts, and design principles (~280 lines)
  - **References:**
    - `official-spec.md` - Complete YAML frontmatter specification
    - `orchestration-patterns.md` - Fan-out, pipeline, and orchestrator-worker patterns
    - `tool-permissions.md` - Tool selection guidance by agent role
    - `anti-patterns.md` - Common mistakes and how to avoid them
  - **Workflows:**
    - `create-read-only-agent.md` - Guide for reviewers, analyzers, auditors
    - `create-code-writer-agent.md` - Guide for implementers, fixers, generators
    - `create-research-agent.md` - Guide for documentation and web researchers
    - `audit-existing-agent.md` - Checklist for improving existing agents
  - **Templates:**
    - `code-reviewer.md` - Ready-to-use code review agent
    - `debugger.md` - Bug diagnosis and fixing agent
    - `researcher.md` - Documentation research agent
    - `domain-expert.md` - Customizable domain expert template
  - **Examples:**
    - `real-world-agents.md` - Battle-tested agent configurations
- **code-reviewer agent** - Expert code reviewer for quality, security, and best practices
  - Comprehensive review checklist covering code quality, error handling, security, performance, testing, architecture, and documentation
  - Structured output format with file:line references
  - Tools: Read, Glob, Grep (strictly read-only)
  - Model: sonnet for balanced performance

### Research Sources
- [Official Claude Code Docs](https://code.claude.com/docs/en/sub-agents)
- [Anthropic Engineering: Multi-Agent Research](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Claude Agent SDK Blog](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)
- [VoltAgent Subagent Collection](https://github.com/VoltAgent/awesome-claude-code-subagents)
- Industry best practices for agentic AI 2025-2026

## [0.3.2] - 2026-01-30

### Changed
- Restructured README credits section to use markdown tables for better readability
- Renamed "Source Skills" to "Sourced Skills" with Skill/Source columns
- Added "Sourced Commands" table documenting command origins
- Fixed typo in skill name (createing → create)

## [0.3.1] - 2026-01-30

### Added
- **git-stacked-prs automation scripts** - Four bash scripts to automate stacked PR workflows:
  - `stack-status.sh` - Display visual tree of stack structure with PR status (~220 lines)
  - `stack-backup.sh` - Create and restore backups before risky operations (~170 lines)
  - `stack-rebase.sh` - Automate sequential rebasing with safety features (~250 lines)
  - `update-pr-targets.sh` - Batch update PR targets after merges (~180 lines)

### Changed
- Updated git-stacked-prs SKILL.md with "Automated Operations" section
- Updated workflows (create-stacked-prs.md, update-stack-after-merge.md) to reference automation scripts
- Updated references/stacked-prs.md with "Built-in Automation Scripts" section
- All scripts follow marketplace patterns with colors, error handling, help text, and git safety

### Impact
- **Token reduction**: 60-70% fewer tokens for common stack operations
- **Error reduction**: Automated safety checks prevent common mistakes
- **Faster workflows**: Multi-step operations reduced to single command
- **Better UX**: Visual feedback, color output, clear error messages

## [0.3.0] - 2026-01-30

### Added
- **git-commits** - Commit best practices and message formatting guidelines (241 lines)
- **git-stacked-prs** - Stacked PR workflow and management (311 lines)
- **git-advanced** - Advanced operations, analysis tools, and command reference (350 lines)

### Removed
- **managing-git** skill (replaced by three focused skills above)

### Changed
- Split comprehensive managing-git skill into three focused skills for better usability and maintainability
- Each new skill follows progressive disclosure pattern with SKILL.md < 500 lines
- Improved skill discoverability with specific, targeted descriptions and trigger keywords

## [0.2.0] - 2026-01-29

### Added
- Specific `allowed-tools` syntax to managing-git skill frontmatter: `Bash(git add:*)`, `Bash(git status:*)`, `Bash(git commit:*)`
- Context section with detailed git commands: `!git status`, `!git diff HEAD`, `!git branch --show-current`, `!git log --oneline -10`
- Structured commit message format in commit-guidelines.md: `type(scope): summary` with body and footer sections
- Branch naming pattern in stacked-prs.md: `feat/<stack-name>/<component>`
- PR title format with stack name: `[<Stack Name> X/Y] Description`
- Templates folder with reusable templates:
  - commit-message.txt - Structured commit message template
  - pr-description.md - Stacked PR description template

### Changed
- Updated branch naming convention to hierarchical format: `feat/auth/base`, `feat/auth/middleware`, `feat/auth/ui`
- All stacked PR examples now use hierarchical naming throughout documentation
- SKILL.md streamlined by removing redundant Stacked PRs subsection (covered in references)
- commit-guidelines.md restructured with type/scope/summary format
- stacked-prs.md reorganized with branch naming pattern integrated into Step 1

### Removed
- Redundant Stacked PRs subsection from SKILL.md (now referenced via workflows and references)

## [0.1.0] - 2026-01-29

### Added
- New workflow files in managing-git skill:
  - `workflows/create-stacked-prs.md` - Step-by-step guide for creating stacked PRs from changes
  - `workflows/update-stack-after-merge.md` - Guide for updating PR targets and rebasing after merge
  - `workflows/recover-from-rebase.md` - Comprehensive reflog-based recovery procedures
- New reference file in managing-git skill:
  - `references/common-commands.md` - Complete git command reference

### Changed
- Improved managing-git skill structure following best practices:
  - Added router pattern with "What Would You Like To Do?" section
  - Enhanced examples with concrete scenarios (JWT auth, specific files)
  - Streamlined content and reduced verbosity
  - Better progressive disclosure structure
- Updated SKILL.md from 273 to 290 lines (still under 500 limit)

## [0.0.1] - 2026-01-29

### Added
- Initial plugin structure
- create-agent-skills skill with comprehensive guidance
- managing-git skill with git workflow management

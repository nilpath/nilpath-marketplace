# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.7] - 2026-04-29

### Added

- **spec-reviewer agent** - New read-only agent (`model: haiku`) that reviews design specifications for completeness, internal consistency, and scope adherence. Used by the `researching` skill after writing `design.md`.
- **docs-library-researcher agent** - Researches external documentation, libraries, and frameworks. Checks project dependencies, looks up official docs via context7, notes best practices and limitations.
- **api-integration-researcher agent** - Researches external APIs, authentication, data formats, rate limits, and existing integration patterns in the codebase.
- **architecture-researcher agent** - Analyzes project architecture, design patterns, and structural impact; identifies reference implementations for significant architectural decisions.
- **researching skill** - Research-first workflow that guides from problem exploration through design spec to implementation handoff. Includes mermaid process flow, agent orchestration guidance, design spec template, and spec self-review step.
- **engineering-principles skill** - Referenced by the `researching` skill for structural and design trade-off decisions.

### Changed

- **README** - Added all 5 agents to the agents table and details section (previously only `code-reviewer` was listed).
- **creating-skills skill** - Renamed from `create-agent-skills` to `creating-skills` for naming consistency
- **creating-skills skill** - Updated for new Claude Code skills spec
  - Added `## Commands → Skills Merge` section: commands and skills are now equivalent, no separate command file needed
  - Expanded frontmatter reference to cover all 14 fields: `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `context`, `agent`, `effort`, `paths`, `hooks`, `shell`
  - Added new reference `invocation-and-arguments.md`: invocation control matrix, argument substitutions (`$ARGUMENTS`, `$N`, named args), shell injection (`` !`cmd` ``), forked subagent context (`context: fork`)
  - Full rewrite of `references/official-spec.md`: complete frontmatter table, string substitution table, shell injection, forked context, live change detection
  - Rewrote `references/skill-structure.md`: removed XML promotion, replaced with markdown heading guidance and updated validation checklist
  - Rewrote `references/core-principles.md`: replaced XML structure principle with markdown heading principle
  - Rewrote `references/common-patterns.md`: removed XML examples, added shell injection, invocation control, and arguments patterns
  - Updated `references/recommended-structure.md`: replaced XML templates with markdown heading templates
  - Updated `templates/simple-skill.md` and `templates/router-skill.md`: replaced XML body with markdown headings
  - Updated `workflows/create-new-skill.md`: removed `.claude/commands/` creation step, added invocation mode selection step, updated validation checklist
  - Updated `workflows/audit-skill.md`: replaced XML checklist criteria with correct markdown heading criteria, removed reference to non-existent `use-xml-tags.md`

## [0.5.6] - 2026-03-04

### Fixed

- **gh-address-comments skill** - GitHub Enterprise API hostname fix
  - `fetch-comments.sh` now detects hostname from git remote and passes `--hostname` to `gh api graphql`
  - Fixes GraphQL queries defaulting to github.com on GitHub Enterprise repos

- **gh-pr-review skill** - GitHub Enterprise API hostname fix
  - Added hostname detection from git remote to `create-review.sh` and `submit-review.sh`
  - `gh api` REST calls now use `--hostname` to target the correct GitHub instance
  - Fixes 404 errors when creating/submitting reviews on GitHub Enterprise

## [0.5.5] - 2026-03-04

### Fixed

- **gh-address-comments skill** - GitHub Enterprise repository path fix
  - `fetch-comments.sh` now uses `nameWithOwner` as primary source for repo owner/name
  - Falls back to `owner.login` + `name` only if `nameWithOwner` is unavailable
  - Fallback to `gh repo view --json nameWithOwner` also uses the same pattern
  - Fixes GraphQL query failures when fetching PR comments on GitHub Enterprise

## [0.5.4] - 2026-02-06

### Fixed

- **gh-pr-review skill** - Complete GitHub Enterprise repository path fix
  - `pr-info.sh` now uses `nameWithOwner` as primary source for repo path
  - Falls back to `owner.login + "/" + name` only if `nameWithOwner` is unavailable
  - Improved regex validation catches malformed paths like `/reponame` or `null/reponame`
  - Fixes 404 errors when creating PR review comments on GitHub Enterprise

## [0.5.3] - 2026-02-06

### Fixed

- **gh-pr-review skill** - GitHub Enterprise support
  - Scripts now dynamically fetch PR URL via `gh pr view` instead of hardcoding `github.com`
  - Updated `create-review.sh` and `submit-review.sh` to work with any GitHub instance
  - Fallback to github.com URL construction if PR URL fetch fails

- **gh-pr-review skill** - Line positioning for PR review comments
  - Added `side` field defaulting to `RIGHT` for comments on additions/modifications
  - Added support for multi-line comments via `start_line` and `start_side`
  - Updated documentation with positioning rules and examples

### Added

- **gh-address-comments skill** - Reply to review threads
  - New script: `reply-to-thread.sh` - Reply to PR review threads via GraphQL
  - Updated workflow with Step 5 for acknowledging addressed comments
  - Enables closing the feedback loop after fixing issues

## [0.5.2] - 2026-02-03

### Added

- **gh-address-comments skill** - Address review/issue comments on open PR for current branch
  - Complements gh-pr-review (creating reviews) with responding to received feedback
  - **Scripts**: `fetch-comments.sh` - Fetch all PR comments via GitHub GraphQL API
  - Fetches: conversation comments, reviews, inline review threads (with resolved/outdated state)
  - Workflow: Fetch → Summarize actionable items → User selects → Apply fixes
  - Adapted from [openai/skills/gh-address-comments](https://github.com/openai/skills/tree/main/skills/.curated/gh-address-comments)

## [0.5.1] - 2026-02-01

### Added

- **creating-mermaid-diagrams skill** - Create, edit, and validate Mermaid diagrams
  - Support for all diagram types: flowchart, sequence, class, state, ER, Gantt, pie, mindmap, timeline, git graph
  - **References**: 12 quick reference files (~50 lines each) with progressive disclosure to official docs
  - **Templates**: 5 starter templates (flowchart, sequence-diagram, class-diagram, architecture-diagram, er-diagram)
  - **Workflows**: create-diagram.md, edit-diagram.md, validate-diagram.md
  - **Scripts**: `validate-mermaid.sh` - Syntax validation via `npx @mermaid-js/mermaid-cli`
  - Styling and theming reference
  - Common patterns and anti-patterns guide

## [0.5.0] - 2026-02-01

### Added

- **gh-pr-review skill** - GitHub PR review operations via gh CLI
  - `pr-info.sh` - Get PR context (number, repo, diff files)
  - `create-review.sh` - Create pending review with line comments
  - `submit-review.sh` - Submit pending review (approve/reject/comment)
  - `references/api-reference.md` - GitHub API documentation

### Changed

- **code-reviewer agent** - Enhanced with GitHub PR line comments capability
  - Added Bash tool access (restricted to gh/git commands via skill)
  - Loads gh-pr-review skill for PR operations
  - Creates PENDING reviews so user can edit before submitting
  - Only adds Critical Issues and Warnings as PR comments (not Suggestions)
  - Always outputs markdown summary alongside PR comments

## [0.4.1] - 2026-01-30

### Changed

- Reorganized agents into category subdirectories for better structure
  - Moved `code-reviewer.md` to `agents/review/code-reviewer.md`

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

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

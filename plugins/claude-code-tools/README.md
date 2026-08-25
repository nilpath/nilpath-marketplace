# Claude Code Tools

A collection of Agents and Skills for coding with Claude.

## Version

0.7.0

## Components

### Agents (12)

| Agent | Description |
| ----- | ----------- |
| **code-reviewer** | Expert code reviewer for quality, security, and best practices. Can add line comments to GitHub PRs. |
| **spec-reviewer** | Reviews design specifications for completeness, internal consistency, and scope adherence. |
| **docs-library-researcher** | Researches external documentation, libraries, and frameworks. Looks up official docs and best practices. |
| **api-integration-researcher** | Researches external APIs, authentication, data formats, rate limits, and existing integration patterns. |
| **architecture-researcher** | Analyzes project architecture, design patterns, and structural impact for significant architectural decisions. |
| **task-decomposer** | Reads an approved design spec and produces a draft ordered list of TDD implementation tasks. Used by the `planning` skill. |
| **plan-reviewer** | Reviews plan.md for completeness, spec alignment, task sizing, decomposition quality, and TDD format. Used by the `planning` skill. |
| **coding-task-agent** | Implements a single coding task from a TDD plan following the red→green→commit cycle. Used by the `executing-plan` skill. |
| **python-task-agent** | Implements a single Python coding task with auto-detection of test runner, virtualenv, and package manager. Used by the `executing-plan` skill. |
| **code-debugger** | Diagnoses failing tests and runtime errors, applies a minimal fix, and confirms resolution. Used by the `executing-plan` skill. |
| **doc-writer** | Writes or updates a single documentation file with source-verified accuracy. Used by the `writing-documentation` and `executing-plan` skills. |
| **doc-auditor** | Audits documentation for accuracy, completeness, clarity, hallucinations, and code quality. Used by the `writing-documentation` skill. |

### Agent Details

**code-reviewer**

- Engineering-principles based audit: SOLID, DRY, KISS, YAGNI, Law of Demeter, and more
- Comprehensive review checklist: code quality, error handling, security, performance, testing, architecture, dead code
- Structured output with `VERDICT: PASS / FAIL` and file:line references for all issues
- Uses `Agent(Explore)` for dead code and caller analysis
- Proactive invocation after code changes
- Tools: Read, Glob, Grep, Bash, Agent(Explore)
- Skills: engineering-principles
- Model: sonnet

**spec-reviewer**
- Checks design specs for incomplete work, internal consistency, and scope adherence
- Returns structured report with "Ready / Needs revisions" verdict
- Used by the `researching` skill after writing `design.md`
- Tools: Read, Glob, Grep
- Model: haiku

**docs-library-researcher**
- Checks project dependencies, looks up official docs via context7, notes best practices and limitations
- Used by the `researching` skill for library and framework investigation
- Tools: Read, Glob, Grep, WebFetch, WebSearch, context7
- Model: sonnet

**api-integration-researcher**
- Investigates API auth, data formats, rate limits, and existing integration code in the codebase
- Used by the `researching` skill when features involve external APIs
- Tools: Read, Glob, Grep, WebFetch, WebSearch
- Model: sonnet

**architecture-researcher**
- Analyzes project structure, design patterns, and architectural impact; identifies reference implementations
- Used by the `researching` skill for features with significant structural decisions
- Tools: Read, Glob, Grep
- Model: sonnet

**task-decomposer**
- Extracts components from a design spec, orders them leaves-first, and formats each as a TDD task block
- Applies `engineering-principles` skill to verify single responsibility and testability
- Flags ambiguous components with `[AMBIGUOUS: ...]` for the planning skill to resolve
- Tools: Read, Glob, Grep, Skill(engineering-principles)
- Model: sonnet

**plan-reviewer**
- Reviews plan.md for completeness, alignment with spec, task sizing, decomposition quality, ordering, and TDD format
- Returns a structured report by category + Ready/Needs revisions verdict
- Focuses on real blockers; ignores wording and style preferences
- Tools: Read, Glob, Grep
- Model: haiku

**coding-task-agent**
- Follows TDD: write failing test → implement → confirm green → commit
- Applies `engineering-principles` to verify single responsibility before implementing
- Reports pass/fail + commit SHA back to the orchestrating skill
- Tools: Read, Write, Edit, Bash, Glob, Grep, Skill(engineering-principles), Skill(git-commits)
- Model: haiku

**python-task-agent**
- Python-specific TDD agent with environment auto-detection (uv/poetry/pytest, virtualenv, conftest.py)
- Same red→green→commit cycle as coding-task-agent
- Tools: Read, Write, Edit, Bash, Glob, Grep, Skill(engineering-principles), Skill(git-commits)
- Model: haiku

**code-debugger**
- Identifies root cause from stack traces, applies minimal fix, re-runs tests to confirm resolution
- Reports root cause + fix summary; stops after one fix attempt if still failing
- Tools: Read, Write, Edit, Bash, Glob, Grep
- Model: sonnet

**doc-writer**
- Writes or updates a single documentation file; reads source files first to verify accuracy
- Stops with `blocked` status if source files are missing or contradict the task description
- Follows RISEN framework: explicit steps, audience calibration, style matching, active voice
- Used by both `writing-documentation` (orchestrated writes) and `executing-plan` (plan.md doc tasks)
- Tools: Read, Write, Edit, Glob, Grep
- Model: haiku

**doc-auditor**
- Audits documentation across 9 dimensions: accuracy, completeness, clarity, coherence, consistency, code quality, hallucinations, relevance, and structure
- Every finding includes a concrete fix suggestion (not just a problem description)
- Read-only; uses `permissionMode: plan` to enforce no-write constraint at harness level
- Tools: Read, Glob, Grep
- Model: sonnet

### Skills (15)

| Skill | Description |
|-------|-------------|
| **researching** | Research-first workflow: explore the problem space, propose approaches, and produce a design spec before any implementation |
| **planning** | Translates an approved design spec into a sequenced list of TDD implementation tasks (2–5 min each), each following a red → green → commit cycle |
| **executing-plan** | Executes an approved plan.md: creates a worktree, reviews for blockers, delegates one task at a time to subagents, code-reviews after each commit, flips plan.md checkboxes as work proceeds, surfaces aggregated review warnings to the user at the end, and creates a PR |
| **using-git-worktrees** | Manages git worktrees for feature development — create, list, and remove worktrees for isolated branches |
| **engineering-principles** | Core software engineering and design principles (SOLID, DRY, KISS, YAGNI). Reference when making design decisions or reviewing code |
| **creating-agents** | Expert guidance for designing and implementing Claude Code subagents |
| **creating-skills** | Expert guidance for creating, writing, and refining Claude Code Skills |
| **creating-mermaid-diagrams** | Create, edit, and validate Mermaid diagrams (flowcharts, sequence, class, ER, etc.) |
| **gh-pr-review** | GitHub PR review operations: create pending reviews with line comments (single and multi-line), submit reviews |
| **gh-address-comments** | Address review/issue comments on the open GitHub PR for the current branch, reply to threads after fixing |
| **git-commits** | Git commit best practices and message formatting guidelines |
| **git-stacked-prs** | Stacked (dependent) pull request workflow and management |
| **git-advanced** | Advanced git operations, analysis tools, recovery, and command reference |
| **performing-code-review** | Orchestrate code review for local branch or PR — delegates to code-reviewer, then optionally posts as PR line comments or a single comment |
| **writing-documentation** | Create, update, and audit technical documentation using an orchestrator-worker pattern — spawns doc-writer agents per file and a doc-auditor after every write |

### Skill Details

**creating-agents** (~280 lines)
- Comprehensive guide for designing and implementing Claude Code subagents
- Core principles: context preservation, parallelization, specialization
- References: official-spec.md, orchestration-patterns.md, tool-permissions.md, anti-patterns.md
- Workflows: create-read-only-agent.md, create-code-writer-agent.md, create-research-agent.md, audit-existing-agent.md
- Templates: code-reviewer.md, debugger.md, researcher.md, domain-expert.md
- Examples: real-world-agents.md with battle-tested configurations

**creating-skills**
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
  - `create-review.sh` - Create pending review with line comments (single-line and multi-line support)
  - `submit-review.sh` - Submit pending review (approve/reject/comment)
- References: api-reference.md with GitHub API details and line positioning rules
- Creates PENDING reviews so user can edit before submitting
- Supports `side` field (RIGHT/LEFT) and `start_line` for multi-line comments

**gh-address-comments**
- Address review/issue comments on open PR for current branch
- Complements gh-pr-review (creating reviews) with responding to reviews
- **Scripts**:
  - `fetch-comments.sh` - Fetch all PR comments via GitHub GraphQL API
  - `reply-to-thread.sh` - Reply to review threads after addressing feedback
- Workflow: Fetch comments → Summarize actionable items → Apply fixes → Reply to threads
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
- [cipherstash/cipherpowers](https://github.com/cipherstash/cipherpowers)
- [Anthropic Agent Skills Documentation](https://code.claude.com/docs/en/skills)

### Sourced Skills

| Skill | Source |
|-------|--------|
| creating-skills | [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) |
| gh-address-comments | [openai/skills](https://github.com/openai/skills/tree/main/skills/.curated/gh-address-comments) |

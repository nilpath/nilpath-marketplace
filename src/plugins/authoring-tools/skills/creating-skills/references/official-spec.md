# Anthropic Official Skill Specification

Source: [code.claude.com/docs/en/skills](https://code.claude.com/docs/en/skills)

## What Is a Skill

A skill is a directory with a `SKILL.md` file. The `name` field (or directory name if omitted) becomes the `/slash-command`. Every SKILL.md has two parts: YAML frontmatter between `---` markers, and markdown content with instructions.

Use **standard markdown headings** for structure. No XML tags.

```markdown
---
name: my-skill
description: What it does and when to use it
---

# My Skill Name

## Quick Start
Immediate actionable guidance...

## Instructions
Step-by-step procedures...

## Examples
Concrete usage examples...
```

## Skill Locations

| Level | Path | Applies to |
|-------|------|-----------|
| Enterprise | See managed settings | All users in organization |
| Personal | `~/.claude/skills/<skill-name>/SKILL.md` | You, across all projects |
| Project | `.claude/skills/<skill-name>/SKILL.md` | This project only |
| Plugin | `<plugin>/skills/<skill-name>/SKILL.md` | Where plugin is enabled |

Enterprise overrides personal; personal overrides project. Plugin skills use a `plugin-name:skill-name` namespace and cannot conflict with other levels.

## Commands → Skills Merge

Custom commands and skills are now equivalent. Both create a `/slash-command`:

```
.claude/commands/deploy.md          → /deploy
.claude/skills/deploy/SKILL.md      → /deploy
```

Existing `.claude/commands/` files keep working. If a skill and command share the same name, the skill takes precedence. Skills are preferred because they support supporting files and invocation control frontmatter.

## Frontmatter Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Our convention: required | Lowercase letters, numbers, hyphens only (max 64 chars). Becomes the `/slash-command`. Defaults to directory name if omitted. |
| `description` | Our convention: required | What it does and when to use it (third person). Combined with `when_to_use`, truncated at 1,536 chars in the skill listing. Defaults to first paragraph if omitted. |
| `when_to_use` | No | Extra trigger phrases appended to `description` in the skill listing. Counts toward the 1,536-char cap. |
| `argument-hint` | No | Hint shown during autocomplete. Example: `[issue-number]` or `[filename] [format]`. |
| `arguments` | No | Named positional args for `$name` substitution. Space-separated string or YAML list. |
| `disable-model-invocation` | No | `true` prevents Claude from auto-loading this skill. Description is excluded from context. Use for side-effect workflows. |
| `user-invocable` | No | `false` hides from the `/` menu. Use for background knowledge. |
| `allowed-tools` | No | Tools Claude can use without prompting while this skill is active. Example: `Bash(git add *) Bash(git commit *)` |
| `model` | No | Override model for this skill's turn. Accepts same values as `/model`. |
| `effort` | No | Override effort level: `low`, `medium`, `high`, `xhigh`, `max`. |
| `context` | No | Set to `fork` to run in an isolated subagent context. |
| `agent` | No | Subagent type when `context: fork`. Built-ins: `Explore`, `Plan`, `general-purpose`. Or any custom agent. |
| `paths` | No | Glob patterns limiting when the skill auto-activates. Comma-separated string or YAML list. |
| `hooks` | No | Hooks scoped to this skill's lifecycle. |
| `shell` | No | Shell for `` ! `command` `` injection blocks: `bash` (default) or `powershell`. |

## Invocation Control

Two fields control who can invoke a skill:

| Frontmatter | You can invoke | Claude can invoke | Description in context |
|-------------|:--------------:|:-----------------:|:----------------------:|
| (default) | Yes | Yes | Always loaded |
| `disable-model-invocation: true` | Yes | No | Never loaded |
| `user-invocable: false` | No | Yes | Always loaded |

Use `disable-model-invocation: true` for workflows with side effects you want to control manually (`/commit`, `/deploy`, `/send-slack`). Use `user-invocable: false` for background knowledge Claude applies automatically.

## String Substitutions

| Variable | Description |
|----------|-------------|
| `$ARGUMENTS` | All arguments passed when invoking. Appended at the end if not present in skill content. |
| `$ARGUMENTS[N]` | Specific argument by 0-based index. |
| `$N` | Shorthand: `$0` = first arg, `$1` = second. |
| `$name` | Named argument declared in the `arguments` frontmatter list. |
| `${CLAUDE_SESSION_ID}` | Current session ID. Useful for logging or session-specific files. |
| `${CLAUDE_EFFORT}` | Current effort level: `low`, `medium`, `high`, `xhigh`, or `max`. |
| `${CLAUDE_SKILL_DIR}` | Directory containing the skill's `SKILL.md`. Use to reference bundled scripts regardless of working directory. |

### Named Arguments Example

```yaml
---
name: migrate-component
description: Migrate a component between frameworks
arguments: [component, from, to]
---

Migrate the $component component from $from to $to.
Preserve all existing behavior and tests.
```

Running `/migrate-component SearchBar React Vue` replaces `$component` with `SearchBar`, `$from` with `React`, `$to` with `Vue`.

### Positional Arguments Example

```yaml
---
name: fix-issue
description: Fix a GitHub issue
disable-model-invocation: true
argument-hint: [issue-number]
---

Fix GitHub issue $ARGUMENTS following our coding standards.

1. Read the issue description
2. Understand the requirements
3. Implement the fix
4. Write tests
5. Create a commit
```

## Shell Injection

Execute shell commands before skill content is sent to Claude. Output replaces the placeholder inline.

**Inline syntax:**

```
!`gh pr diff`
```

**Block syntax (multi-line):**

````
```!
node --version
git status --short
```
````

### Example with Shell Injection

```yaml
---
name: pr-summary
description: Summarize the current pull request
context: fork
agent: Explore
allowed-tools: Bash(gh *)
---

## Pull Request Context

- Diff: !`gh pr diff`
- Comments: !`gh pr view --comments`
- Changed files: !`gh pr diff --name-only`

## Task

Summarize this pull request for a reviewer who has not seen it before.
```

When this skill runs, each `` ! `command` `` executes immediately and its output replaces the placeholder before Claude sees anything.

To disable shell injection: set `"disableSkillShellExecution": true` in settings.

> **Note:** When documenting shell injection syntax inside a skill file, add a space before the backtick (` ! \`cmd\` `) to prevent execution during skill load.

## Forked Subagent Context

Add `context: fork` to run a skill in an isolated subagent. Results are summarized and returned to the main conversation.

```yaml
---
name: deep-research
description: Research a topic thoroughly using codebase search
context: fork
agent: Explore
---

Research $ARGUMENTS thoroughly:

1. Find relevant files using Glob and Grep
2. Read and analyze the code
3. Summarize findings with specific file references and line numbers
```

The `agent` field sets which subagent type handles execution (model, tools, permissions). Options: `Explore`, `Plan`, `general-purpose`, or any custom agent from `.claude/agents/`. Defaults to `general-purpose` if omitted.

> **Warning:** `context: fork` only works for skills with explicit task instructions. Skills containing only guidelines or reference content (no actionable prompt) return without meaningful output.

## Progressive Disclosure

Keep `SKILL.md` under 500 lines. Reference supporting files from `SKILL.md`:

```
my-skill/
├── SKILL.md           # Main instructions (required)
├── reference.md       # Detailed docs — loaded when needed
├── examples.md        # Usage examples — loaded when needed
└── scripts/
    └── helper.sh      # Executed, not loaded into context
```

Reference files from `SKILL.md` so Claude knows what they contain and when to load them:

```markdown
## Additional Resources

For complete API details, see [reference.md](reference.md).
For usage examples, see [examples.md](examples.md).
```

## Live Change Detection

Claude Code watches skill directories for file changes. Adding, editing, or removing a skill under `~/.claude/skills/`, project `.claude/skills/`, or an `--add-dir` directory takes effect within the current session without restarting.

Exception: creating a top-level skills directory that did not exist when the session started requires restarting Claude Code.

## Restricting Tool Access

Use `allowed-tools` to pre-approve specific tools for a skill:

```yaml
---
name: commit
description: Stage and commit current changes
disable-model-invocation: true
allowed-tools: Bash(git add *) Bash(git commit *) Bash(git status *)
---
```

Permission syntax: `Bash(git add *)` allows `git add` with any arguments. See the permissions reference for full syntax.

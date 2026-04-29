# Invocation Control, Arguments, and Shell Injection

## Invocation Control

Two frontmatter fields control who can invoke a skill and when its description loads into context.

| Frontmatter | You can invoke | Claude can invoke | Description in context |
|-------------|:--------------:|:-----------------:|:----------------------:|
| (default) | Yes | Yes | Always loaded |
| `disable-model-invocation: true` | Yes | No | Never loaded |
| `user-invocable: false` | No | Yes | Always loaded |

### When to use `disable-model-invocation: true`

Use for workflows with side effects or timing you want to control:

```yaml
---
name: deploy
description: Deploy the application to production
disable-model-invocation: true
allowed-tools: Bash(./scripts/deploy.sh *)
---

Deploy $ARGUMENTS to production:

1. Run the test suite
2. Build the application
3. Push to the deployment target
4. Verify the deployment succeeded
```

The description is excluded from Claude's context entirely, so Claude will never suggest running `/deploy` automatically.

### When to use `user-invocable: false`

Use for background knowledge that Claude should apply automatically but users shouldn't invoke directly:

```yaml
---
name: api-conventions
description: API design patterns for this codebase. Apply when writing or reviewing API endpoints.
user-invocable: false
---

When writing API endpoints:
- Use RESTful naming conventions
- Return consistent error formats with `{ error, message, code }`
- Include request validation before business logic
```

## Arguments

### Basic: `$ARGUMENTS`

The simplest way to pass arguments — everything after the skill name is available as `$ARGUMENTS`:

```yaml
---
name: fix-issue
description: Fix a GitHub issue
disable-model-invocation: true
argument-hint: [issue-number]
---

Fix GitHub issue $ARGUMENTS following our coding standards.

1. Read the issue description
2. Implement the fix
3. Write tests
4. Create a commit
```

Running `/fix-issue 123` passes "123" as `$ARGUMENTS`.

### Positional: `$ARGUMENTS[N]` or `$N`

Access specific arguments by 0-based index:

```yaml
---
name: migrate-component
description: Migrate a component from one framework to another
argument-hint: [component] [from-framework] [to-framework]
---

Migrate the $ARGUMENTS[0] component from $ARGUMENTS[1] to $ARGUMENTS[2].
Preserve all existing behavior and tests.
```

Shorthand: `$0`, `$1`, `$2` are equivalent to `$ARGUMENTS[0]`, `$ARGUMENTS[1]`, `$ARGUMENTS[2]`.

Multi-word arguments use shell-style quoting: `/migrate-component "Search Bar" React Vue` makes `$0` expand to `Search Bar`.

### Named: `arguments` frontmatter

Declare named positional arguments for readable substitution:

```yaml
---
name: migrate-component
description: Migrate a component from one framework to another
arguments: [component, from, to]
argument-hint: [component] [from-framework] [to-framework]
---

Migrate the $component component from $from to $to.
Preserve all existing behavior and tests.
```

Names map to positions in order: `$component` = first arg, `$from` = second, `$to` = third.

### Session and skill variables

| Variable | Description |
|----------|-------------|
| `${CLAUDE_SESSION_ID}` | Current session ID. Use for session-specific log files or output directories. |
| `${CLAUDE_EFFORT}` | Active effort level. Use to adapt instructions to the effort setting. |
| `${CLAUDE_SKILL_DIR}` | Directory containing the skill's `SKILL.md`. Use to reference bundled scripts regardless of working directory. |

**Example using `${CLAUDE_SKILL_DIR}`:**

```yaml
---
name: validate-schema
description: Validate JSON files against this project's schema
allowed-tools: Bash(python *)
---

Run the schema validator:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/validate.py $ARGUMENTS
```
```

## Shell Injection

Execute shell commands before skill content reaches Claude. Output replaces the placeholder.

### Inline syntax

```
!`command`
```

### Block syntax (multi-line)

````
```!
command1
command2
```
````

### Example: PR summary with live context

```yaml
---
name: pr-summary
description: Summarize the current pull request
context: fork
agent: Explore
allowed-tools: Bash(gh *)
---

## Pull Request Context

- Branch: !`git branch --show-current`
- Diff: !`gh pr diff`
- Comments: !`gh pr view --comments`
- Changed files: !`gh pr diff --name-only`

## Task

Summarize this pull request for a reviewer who hasn't seen it yet.
Include: what changed, why, and what to watch for in review.
```

Each `` !`command` `` executes at load time, before Claude sees any content. The skill becomes fully rendered with actual data before it runs.

### Preventing accidental execution in documentation

When writing skill content that *shows* the shell injection syntax as an example (rather than using it), add a space before the backtick:

```
! `git status`   ← space prevents execution; shown as documentation
!`git status`    ← no space, executes at load time
```

To disable shell injection globally: set `"disableSkillShellExecution": true` in settings.

## Forked Subagent Context

Add `context: fork` to run a skill in an isolated subagent. Results are summarized and returned to the main conversation. The main conversation context is unaffected.

```yaml
---
name: security-audit
description: Audit the codebase for security vulnerabilities
context: fork
agent: Explore
---

Perform a security audit of $ARGUMENTS (or the full codebase if no argument given):

1. Search for hardcoded secrets, API keys, and credentials
2. Check for SQL injection patterns
3. Review authentication and authorization logic
4. Identify OWASP Top 10 vulnerabilities
5. Report findings with file paths and line numbers
```

### `agent` field options

| Agent | Best for |
|-------|----------|
| `Explore` | Research, codebase search, read-only analysis |
| `Plan` | Planning and design tasks |
| `general-purpose` | Default — balanced tools and permissions |
| Custom agent name | Any agent defined in `.claude/agents/` |

> **Warning:** `context: fork` only makes sense for skills with explicit task instructions. A skill containing only guidelines or conventions (no actionable prompt) will return without meaningful output.

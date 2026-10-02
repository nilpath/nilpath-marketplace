# Official Subagent Specification

Complete reference for Claude Code subagent YAML frontmatter and configuration.

## File Format

Subagent files are Markdown with YAML frontmatter:

```markdown
---
name: agent-name
description: When to use this agent
tools: Read, Grep, Glob
model: sonnet
---

System prompt goes here. This becomes the agent's instructions.
```

## Required Fields

### name

Unique identifier for the agent.

**Rules:**
- Lowercase letters, numbers, and hyphens only
- Must be unique across all loaded agents
- Used to reference agent explicitly

**Examples:**
- `code-reviewer`
- `test-runner`
- `db-query-validator`

### description

Tells Claude when to delegate to this agent. Critical for automatic delegation.

**Best practices:**
- Include what the agent does
- Include when to use it
- Add trigger keywords users might say
- Use "proactively" to encourage automatic delegation

**Good example:**
```yaml
description: Reviews code for quality, security, and best practices. Use proactively after code changes or when user mentions review, audit, or code quality.
```

**Bad example:**
```yaml
description: Helps with code
```

## Optional Fields

### tools

Specifies which tools the agent can use. If omitted, inherits all tools from main conversation (including MCP tools).

**Available tools:**

| Tool | Description |
| ---- | ----------- |
| Read | Read file contents |
| Write | Create or overwrite files |
| Edit | Modify existing files |
| Bash | Execute shell commands |
| Glob | Find files by pattern |
| Grep | Search file contents |
| WebFetch | Fetch web page content |
| WebSearch | Search the web |
| TodoWrite | Manage task lists |
| Task | Spawn subagents (rarely used) |
| NotebookEdit | Edit Jupyter notebooks |

**Format options:**

```yaml
# Comma-separated list
tools: Read, Grep, Glob

# YAML array
tools:
  - Read
  - Grep
  - Glob
```

**Tool aliases:**

| Alias | Expands to |
| ----- | ---------- |
| `Read-only tools` | Read, Grep, Glob |

### disallowedTools

Tools to explicitly deny, removed from inherited or specified list.

```yaml
# Inherit all tools except Write and Edit
disallowedTools: Write, Edit
```

### model

Which model the agent uses.

| Value | Description |
| ----- | ----------- |
| `haiku` | Fast, low-cost (Claude 3.5 Haiku) |
| `sonnet` | Balanced capability/speed (Claude 3.5/4 Sonnet) |
| `opus` | Most capable (Claude Opus 4.5) |
| `inherit` | Use main conversation model (default) |

**Selection guidance:**
- **haiku**: Read-only exploration, simple searches
- **sonnet**: Code review, most implementation tasks
- **opus**: Complex reasoning, architectural decisions
- **inherit**: When task complexity varies

### permissionMode

Controls how the agent handles permission prompts.

| Mode | Behavior |
| ---- | -------- |
| `default` | Standard permission checking with prompts |
| `acceptEdits` | Auto-accept file edits |
| `dontAsk` | Auto-deny permission prompts |
| `bypassPermissions` | Skip all permission checks |
| `plan` | Plan mode (read-only exploration) |

**Warning:** Use `bypassPermissions` with extreme caution. It allows the agent to execute any operation without approval.

**Note:** If the parent uses `bypassPermissions`, this takes precedence and cannot be overridden.

### skills

Skills to preload into the agent's context at startup.

```yaml
skills:
  - api-conventions
  - error-handling-patterns
```

The full content of each skill is injected into the agent's context, not just made available for invocation. Subagents don't inherit skills from the parent conversation; you must list them explicitly.

### hooks

Lifecycle hooks scoped to this agent. Hooks run only while this specific agent is active.

**Available hook events in frontmatter:**

| Event | Matcher | When it fires |
| ----- | ------- | ------------- |
| `PreToolUse` | Tool name | Before agent uses a tool |
| `PostToolUse` | Tool name | After agent uses a tool |
| `Stop` | (none) | When agent finishes |

**Example: Validate Bash commands**

```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-command.sh"
```

**Example: Run linter after edits**

```yaml
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "./scripts/run-linter.sh"
```

**Hook exit codes:**
- `0` - Success, continue
- `1` - Error (logged but continues)
- `2` - Block the operation (for PreToolUse)

## System Prompt (Body)

The markdown body becomes the agent's system prompt.

**What agents receive:**
- This system prompt
- Basic environment details (working directory)
- NOT the full Claude Code system prompt

**Best practices:**
- Be specific about what to do when invoked
- Include step-by-step process
- Specify output format
- Include constraints (what NOT to do)

**Example:**

```markdown
You are a code reviewer ensuring high standards of quality and security.

When invoked:
1. Run `git diff` to see recent changes
2. Focus on modified files
3. Begin review immediately

Review checklist:
- Code clarity and readability
- Proper error handling
- Security vulnerabilities
- Performance considerations

Output format:
- Critical issues (must fix)
- Warnings (should fix)
- Suggestions (consider)

Constraints:
- Do not modify any files
- Do not run tests
- Focus only on the changed code
```

## Storage Priority

When multiple agents share the same name:

| Priority | Location | Scope |
| -------- | -------- | ----- |
| 1 (highest) | `--agents` CLI flag | Current session |
| 2 | `.claude/agents/` | Current project |
| 3 | `~/.claude/agents/` | All your projects |
| 4 (lowest) | Plugin `agents/` | Where plugin enabled |

## CLI-Defined Agents

Pass agents as JSON when launching Claude Code:

```bash
claude --agents '{
  "code-reviewer": {
    "description": "Expert code reviewer. Use proactively after code changes.",
    "prompt": "You are a senior code reviewer...",
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "model": "sonnet"
  }
}'
```

Note: Use `prompt` for the system prompt (equivalent to markdown body).

## Loading Agents

Agents are loaded at session start. To load new agents without restarting:

1. Run `/agents` command
2. Or restart Claude Code session

## Disabling Agents

Prevent Claude from using specific agents in settings:

```json
{
  "permissions": {
    "deny": ["Task(Explore)", "Task(my-custom-agent)"]
  }
}
```

Or via CLI:

```bash
claude --disallowedTools "Task(Explore)"
```

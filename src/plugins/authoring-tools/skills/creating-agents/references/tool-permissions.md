# Tool Permissions by Role

Guide for selecting appropriate tools for different agent roles. The principle is **minimal necessary access** - grant only what the task requires.

## Quick Reference

| Role | Tools | Use Case |
| ---- | ----- | -------- |
| Reviewer | Read, Grep, Glob | Code review, audits, analysis |
| Explorer | Read, Grep, Glob, Bash(read-only) | Codebase navigation, search |
| Researcher | Read, Grep, Glob, WebFetch, WebSearch | Documentation, external research |
| Implementer | Read, Write, Edit, Bash, Glob, Grep | Code changes, feature work |
| Test Runner | Read, Bash, Glob, Grep | Running and analyzing tests |
| Full Access | All tools | Complex multi-step tasks |

## Available Tools

### Read-Only Tools

**Read**
- Read file contents
- Safe for any agent
- Use case: Viewing code, configs, docs

**Grep**
- Search file contents with regex
- Safe for any agent
- Use case: Finding patterns, code search

**Glob**
- Find files by pattern
- Safe for any agent
- Use case: File discovery, project navigation

### Write Tools

**Write**
- Create or overwrite files
- Risk: Can destroy existing content
- Use case: Creating new files, generating code

**Edit**
- Modify existing files
- Risk: Can corrupt code
- Use case: Targeted code changes, refactoring

### Execution Tools

**Bash**
- Execute shell commands
- Risk: Can run any command, modify system
- Use case: Running tests, builds, git operations

**Conditional Bash access:**
```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-command.sh"
```

### Web Tools

**WebFetch**
- Fetch web page content
- Risk: Can access internal URLs if exposed
- Use case: Documentation lookup, API docs

**WebSearch**
- Search the web
- Risk: Minimal (read-only)
- Use case: Finding examples, research

### Other Tools

**TodoWrite**
- Manage task lists
- Risk: Minimal (organizational)
- Use case: Task tracking

**NotebookEdit**
- Edit Jupyter notebooks
- Risk: Similar to Edit
- Use case: Data science workflows

**Task**
- Spawn subagents
- Risk: Recursive delegation
- Use case: Rarely needed for subagents

## Role-Specific Configurations

### Code Reviewer

Read-only analysis with git access for diffs.

```yaml
name: code-reviewer
tools: Read, Grep, Glob
disallowedTools: Write, Edit, Bash
```

If you need git diff:
```yaml
tools: Read, Grep, Glob, Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: |
            #!/bin/bash
            INPUT=$(cat)
            COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
            # Only allow git commands
            if [[ "$COMMAND" != git* ]]; then
              echo "Only git commands allowed" >&2
              exit 2
            fi
            exit 0
```

### Security Auditor

Focused on security-relevant file access.

```yaml
name: security-auditor
tools: Read, Grep, Glob
```

System prompt should focus on:
- Environment variables and secrets
- Authentication logic
- Input validation
- SQL/command injection risks

### Documentation Researcher

Web and file access, no code modification.

```yaml
name: doc-researcher
tools: Read, Grep, Glob, WebFetch, WebSearch
```

### Test Runner

Needs Bash for running tests, but constrained.

```yaml
name: test-runner
tools: Read, Bash, Glob, Grep
```

Consider constraining Bash to test commands only via hooks.

### Bug Fixer

Full code access to diagnose and fix.

```yaml
name: bug-fixer
tools: Read, Write, Edit, Bash, Glob, Grep
```

### Database Query Agent

Bash for queries, but read-only validation.

```yaml
name: db-reader
tools: Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-readonly-query.sh"
```

Validation script:
```bash
#!/bin/bash
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Block write operations
if echo "$COMMAND" | grep -iE '\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b' > /dev/null; then
  echo "Blocked: Write operations not allowed" >&2
  exit 2
fi

exit 0
```

## Inheritance vs Explicit

### Inheriting Tools (Omit `tools` field)

```yaml
name: general-helper
description: General purpose helper
# No tools field - inherits all from main conversation
```

**When to inherit:**
- Agent needs the same capabilities as main conversation
- You want MCP tools included
- Task requirements may vary

### Explicit Tool List

```yaml
name: focused-agent
tools: Read, Grep, Glob
```

**When to be explicit:**
- Security-sensitive tasks
- Read-only agents
- Specialized roles with clear boundaries

## Tool Combinations

### Minimal Read-Only
```yaml
tools: Read, Grep, Glob
```
For: Reviewers, auditors, analyzers

### Read + Bash (Constrained)
```yaml
tools: Read, Grep, Glob, Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-bash.sh"
```
For: Test runners, git operations, build verification

### Read + Web
```yaml
tools: Read, Grep, Glob, WebFetch, WebSearch
```
For: Documentation researchers, external info gathering

### Full Write Access
```yaml
tools: Read, Write, Edit, Bash, Glob, Grep
```
For: Implementers, fixers, generators

### Everything
```yaml
# Omit tools field to inherit all
# Or explicitly list all tools
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch, TodoWrite
```
For: General-purpose agents handling varied tasks

## Using disallowedTools

Deny specific tools while inheriting the rest:

```yaml
# Inherit all tools except destructive ones
disallowedTools: Write, Edit, Bash
```

Useful when:
- You want most capabilities but need to block specific tools
- MCP tools should be available except for certain operations
- Creating a "safe mode" variant of a full-access agent

## Best Practices

1. **Default to minimal** - Start with read-only, add as needed
2. **Consider the attack surface** - What could go wrong with each tool?
3. **Use hooks for nuance** - When you need Bash but only certain commands
4. **Test permissions** - Verify agent can't access what it shouldn't
5. **Document choices** - Explain why specific tools are included/excluded

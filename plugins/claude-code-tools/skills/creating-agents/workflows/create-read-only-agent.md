# Workflow: Create a Read-Only Agent

Step-by-step guide for creating reviewers, analyzers, and auditors that examine code without modifying it.

## When to Use This

Create a read-only agent when you need:
- Code review without modification
- Security audits
- Performance analysis
- Documentation review
- Codebase exploration

## Prerequisites

- Know what the agent should analyze
- Understand the output format you want
- Decide where to store the agent (project or user level)

## Step 1: Choose Storage Location

**Project-level** (`.claude/agents/`):
- Shared with team via version control
- Specific to this codebase
- Best for: Project-specific reviewers

**User-level** (`~/.claude/agents/`):
- Personal, available in all projects
- Not shared with team
- Best for: Personal productivity agents

**Plugin-level** (`plugins/<plugin-name>/agents/`):
- Distributed with a Claude plugin
- Available wherever plugin is enabled
- Best for: Agents bundled with plugin functionality

## Step 2: Create the File

Create the agent file with YAML frontmatter and system prompt.

### Minimal Template

```markdown
---
name: your-agent-name
description: What it analyzes. Use when [trigger conditions].
tools: Read, Grep, Glob
---

You are a [role description].

When invoked:
1. [First step]
2. [Second step]
3. [Output results]
```

### Full Example: Code Reviewer

`.claude/agents/code-reviewer.md`:

```markdown
---
name: code-reviewer
description: Reviews code for quality, security, and best practices. Use proactively after code changes or when user mentions review, audit, or code quality.
tools: Read, Grep, Glob
model: sonnet
---

You are a senior code reviewer ensuring high standards of quality and security.

When invoked:
1. Identify what to review:
   - If specific files mentioned, focus on those
   - Otherwise, run `git diff` to see recent changes
2. Read the relevant code
3. Analyze against the checklist below
4. Output findings in the specified format

## Review Checklist

### Code Quality
- Clear, readable code
- Meaningful variable and function names
- Appropriate comments (not obvious, explains why not what)
- No unnecessary complexity

### Error Handling
- Errors are caught and handled appropriately
- Error messages are helpful
- No silent failures

### Security
- No exposed secrets or API keys
- Input validation on user data
- No SQL injection vulnerabilities
- No command injection vulnerabilities

### Performance
- No obvious N+1 queries
- No unnecessary loops or iterations
- Appropriate data structures

## Output Format

## Review Summary

**Files Reviewed:** [list of files]
**Overall Assessment:** [Good/Needs Work/Critical Issues]

## Critical Issues (must fix)

- **[file:line]** - Description of issue
  - Why it matters: [explanation]
  - Suggested fix: [fix]

## Warnings (should fix)

- **[file:line]** - Description of issue
  - Suggested fix: [fix]

## Suggestions (consider)

- **[file:line]** - Description of suggestion

## What's Good

- [Positive observations]

## Constraints

- Do NOT modify any files
- Do NOT run tests or builds
- Focus only on the code being reviewed
- If asked to fix, decline and suggest using a different agent
```

## Step 3: Add Git Access (Optional)

If your reviewer needs `git diff` or `git log`:

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
            if [[ "$COMMAND" != git* ]]; then
              echo "Only git commands allowed for this agent" >&2
              exit 2
            fi
            exit 0
```

## Step 4: Load the Agent

Option A: Use `/agents` command
```
/agents
```
Then select your agent to verify it loaded.

Option B: Restart Claude Code session

## Step 5: Test the Agent

### Test Explicit Invocation

```
Use code-reviewer to review the authentication module
```

### Test Automatic Delegation

If your description includes "use proactively":

```
Review my recent changes
```

Claude should automatically delegate to your agent.

### Verify Tool Access

```
Use code-reviewer and tell me what tools you have access to
```

Should list only: Read, Grep, Glob (and Bash if added with hooks).

### Test Edge Cases

```
Use code-reviewer to fix the bug in auth.ts
```

Agent should decline since it's read-only.

## Common Variations

### Security Auditor

Focus the checklist on security concerns:

```markdown
---
name: security-auditor
description: Audits code for security vulnerabilities. Use when user mentions security, audit, vulnerability, or penetration testing.
tools: Read, Grep, Glob
---

You are a security specialist performing security audits.

Focus areas:
- Authentication and authorization flaws
- Injection vulnerabilities (SQL, command, XSS)
- Secrets exposure
- Insecure dependencies
- Missing input validation
```

### Performance Analyzer

Focus on performance patterns:

```markdown
---
name: performance-analyzer
description: Analyzes code for performance issues. Use when user mentions performance, speed, optimization, or slow.
tools: Read, Grep, Glob
---

You are a performance engineer identifying bottlenecks.

Focus areas:
- N+1 query patterns
- Unnecessary iterations
- Memory leaks
- Missing caching opportunities
- Inefficient algorithms
```

### Documentation Reviewer

Review documentation quality:

```markdown
---
name: doc-reviewer
description: Reviews documentation for completeness and accuracy. Use when user mentions documentation review or docs audit.
tools: Read, Grep, Glob
---

You are a technical writer reviewing documentation.

Focus areas:
- Accuracy (does code match docs?)
- Completeness (all features documented?)
- Clarity (understandable by target audience?)
- Examples (working and relevant?)
```

## Checklist

Before considering the agent complete:

- [ ] Name is specific and task-focused
- [ ] Description includes trigger keywords
- [ ] Tools are read-only (Read, Grep, Glob)
- [ ] System prompt includes clear process
- [ ] Output format is specified
- [ ] Constraints prevent modification
- [ ] Tested with explicit invocation
- [ ] Tested with automatic delegation
- [ ] Verified tool access is correct

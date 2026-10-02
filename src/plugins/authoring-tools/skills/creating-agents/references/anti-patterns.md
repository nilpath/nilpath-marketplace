# Anti-Patterns to Avoid

Common mistakes when creating subagents and how to fix them.

## Anti-Pattern 1: Vague Description

### The Problem

```yaml
description: Helps with code
```

Claude doesn't know when to delegate because "helps with code" could mean anything.

### Why It Fails

- No trigger keywords for automatic delegation
- Competes with every other code-related agent
- User must explicitly request by name

### The Fix

```yaml
description: Reviews code for quality, security, and best practices. Use proactively after code changes or when user mentions review, audit, or code quality.
```

Include:
- What it does specifically
- When to use it
- Trigger keywords users might say

## Anti-Pattern 2: Over-Broad Tool Access

### The Problem

```yaml
name: code-reviewer
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch
```

A code reviewer doesn't need Write, Edit, Bash, or web tools.

### Why It Fails

- Security risk: Agent can modify what it reviews
- Confusion: Agent might try to fix instead of report
- Unfocused: Too many options reduce quality

### The Fix

```yaml
name: code-reviewer
tools: Read, Grep, Glob
```

Grant only what the task requires. If the reviewer needs `git diff`:

```yaml
tools: Read, Grep, Glob, Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/allow-git-only.sh"
```

## Anti-Pattern 3: No Verification Strategy

### The Problem

```markdown
You are a code fixer. Fix bugs when asked.
```

No way to know if the fix worked or introduced regressions.

### Why It Fails

- Agent might declare success without verification
- Regressions go unnoticed
- User can't trust the output

### The Fix

```markdown
You are a code fixer. When fixing bugs:

1. Understand the issue
2. Locate the root cause
3. Apply minimal fix
4. Verify the fix:
   - Run relevant tests
   - Manually test the specific scenario
   - Check for regressions
5. Report what was fixed and verification results
```

Include verification steps in the system prompt.

## Anti-Pattern 4: Premature Multi-Agent Complexity

### The Problem

Creating 5 specialized agents for a task a single agent could handle.

### Why It Fails

- Coordination overhead exceeds benefit
- Context fragmentation
- Harder to debug
- Slower overall execution

### The Fix

Start with a single well-designed agent. Add more only when you hit clear limitations:

- Context overflow
- Truly independent parallel tasks
- Genuinely different expertise needed

**Rule of thumb:** If you can describe the task in one sentence, one agent is probably enough.

## Anti-Pattern 5: Generic Naming

### The Problem

```yaml
name: helper
name: assistant
name: utility
name: code-agent
```

### Why It Fails

- Hard to discover via description
- Unclear what triggers delegation
- Multiple agents might have similar vague names

### The Fix

Use specific, task-focused names:

- `code-reviewer`
- `test-runner`
- `security-auditor`
- `migration-assistant`
- `api-doc-generator`

**Naming convention:** `[domain]-[action]` or `[action]-[target]`

## Anti-Pattern 6: Missing Context in Prompt

### The Problem

```markdown
You are a code reviewer. Review code.
```

### Why It Fails

- No guidance on what to look for
- No output format
- No process to follow
- Different invocations produce inconsistent results

### The Fix

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
## Critical Issues (must fix)
- [file:line] Description

## Warnings (should fix)
- [file:line] Description

## Suggestions (consider)
- [file:line] Description

Constraints:
- Do not modify files
- Do not run tests
- Focus only on changed code
```

## Anti-Pattern 7: Infinite Loop Potential

### The Problem

An agent that can spawn more agents without limits, or that retries indefinitely on failure.

### Why It Fails

- Token consumption spirals
- User loses visibility
- May never terminate

### The Fix

1. **Don't give Task tool to subagents** (they can't spawn others by default anyway)
2. **Set clear termination conditions** in the prompt
3. **Limit retries** explicitly

```markdown
If you cannot find the information after 3 search attempts, report what you found and stop.

Never spawn additional subagents - complete the task yourself or report what you couldn't find.
```

## Anti-Pattern 8: Ignoring Model Selection

### The Problem

Using Opus (most expensive) for simple file searches, or Haiku for complex reasoning.

### Why It Fails

- Wasted cost on simple tasks
- Poor results when capability is insufficient
- Inconsistent behavior

### The Fix

Match model to task:

| Task | Model | Why |
| ---- | ----- | --- |
| File search, simple grep | haiku | Fast, cheap, sufficient |
| Code review, analysis | sonnet | Good balance |
| Complex reasoning, architecture | opus | Needs capability |
| Varies by invocation | inherit | Flexibility |

```yaml
# Fast exploration agent
model: haiku

# Complex reasoning agent
model: opus

# General-purpose agent
model: inherit
```

## Anti-Pattern 9: Assuming User Context

### The Problem

```markdown
Continue working on the authentication feature we discussed.
```

### Why It Fails

Subagents don't inherit the main conversation context. They only receive their system prompt plus the task description from the orchestrator.

### The Fix

Provide complete context in the delegation:

```markdown
When delegating to this agent, include:
- Specific file paths to work with
- Relevant code snippets or patterns
- Clear success criteria
- Any constraints from the main conversation
```

## Anti-Pattern 10: No Graceful Failure

### The Problem

Agent stops or errors without useful information when it can't complete the task.

### Why It Fails

- User doesn't know what went wrong
- Can't resume or work around the issue
- Wasted effort

### The Fix

```markdown
If you cannot complete the task:
1. Report exactly what you tried
2. Explain why it didn't work
3. Suggest alternative approaches
4. Return partial results if available

Never just stop or error without explanation.
```

## Anti-Pattern Checklist

When creating a new agent, verify:

- [ ] Description is specific with trigger keywords
- [ ] Tools are minimal for the task
- [ ] System prompt includes verification steps
- [ ] Single agent unless multi-agent is clearly needed
- [ ] Name is specific and task-focused
- [ ] Prompt provides complete context and process
- [ ] No infinite loop potential
- [ ] Model matches task complexity
- [ ] Doesn't assume main conversation context
- [ ] Handles failures gracefully

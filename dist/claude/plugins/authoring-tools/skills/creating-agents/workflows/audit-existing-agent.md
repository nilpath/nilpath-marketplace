# Workflow: Audit an Existing Agent

Step-by-step guide for reviewing and improving existing subagents against best practices.

## When to Use This

Audit an agent when:
- Agent isn't being triggered when expected
- Agent produces inconsistent results
- Agent takes too long or uses too many tokens
- Agent does things it shouldn't
- You're inheriting agents from another team
- Regular maintenance review

## Step 1: Locate the Agent File

Establish workspace or personal scope using the `AskUserQuestion` tool if unspecified. Read the existing file without modifying it. Record its path, intended client, and actual format:

- Markdown with YAML frontmatter: inspect native keys and expected client suffix.
- TOML with `name`, `description`, and `developer_instructions`: Codex custom agent.
- `.md.j2` with canonical `targets`/tools/model tiers: marketplace source, not native configuration.

Cross-check content and extension; do not trust either alone. A Claude file found while using Copilot is not automatically a Copilot agent. **Report mismatched harnesses, unsupported fields, and permission semantics before proposing changes. Never silently convert a format or drop restrictions.** Confirm any migration or overwrite with the user.


```bash
# Project agents
ls .claude/agents/

# User agents
ls ~/.claude/agents/

```

Check which agents are loaded in Claude Code:
```text
/agents
```


See [authoring-targets.md](../references/authoring-targets.md) for the separate opt-in source-authoring path.

## Step 2: Review Native Configuration

### Check Required Fields

| Field | Requirement | Common Issues |
| ----- | ----------- | ------------- |
| `name` | Lowercase, hyphens | Spaces, uppercase, special chars |
| `description` | Specific, trigger keywords | Vague, missing "when to use" |



Parse YAML frontmatter and verify fields against the Claude native specification, including tools, model, permission mode, preloaded skills, and hooks.


### Audit Questions

- [ ] Is the name specific and task-focused?
- [ ] Does the description include what AND when?
- [ ] Are there clear trigger keywords?
- [ ] Does "use proactively" make sense for this agent?

### Description Quality Check

**Red flags:**
- Too vague: “Helps with code”
- No trigger keywords: “Reviews code”
- Too broad: “Does everything related to development”

**Good example:**
Configuration fragment (not a complete agent):
```yaml

description: Reviews code for quality, security, and best practices. Use proactively after code changes or when user mentions review, audit, or code quality.

```

## Step 3: Review Tool Access

### Audit Questions

- [ ] Does the agent need all the tools it has?
- [ ] Is it missing tools it needs?
- [ ] Are write tools appropriate for this agent's purpose?
- [ ] Is command execution necessary, and is it independently constrained?

### Tool Appropriateness Matrix


| Agent Type | Should Have | Should NOT Have |
| ---------- | ----------- | --------------- |
| Reviewer | Read, Grep, Glob | Write, Edit |
| Researcher | Read, Grep, Glob, WebFetch | Write, Edit |
| Implementer | Read, Write, Edit, Bash | (depends on scope) |
| Auditor | Read, Grep, Glob | Write, Edit, Bash |

### Check for Over-Privileged Access

```yaml
# Over-privileged reviewer
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch

# Appropriate reviewer
tools: Read, Grep, Glob
```


## Step 4: Review Role Instructions


Read the entire Markdown body after the closing frontmatter marker.


### Structure Check

- [ ] Clear role definition?
- [ ] Step-by-step process?
- [ ] Output format specified?
- [ ] Constraints defined?
- [ ] Edge cases handled?

### Content Quality Check

**Red flags:**
```markdown
# Too brief
You are a code reviewer. Review code.

# No process
You review code for quality.

# No output format
Provide feedback on the code.
```

**Good structure:**
```markdown
You are a [specific role].

## When Invoked
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Output Format
[Specific format]

## Constraints
- [Constraint 1]
- [Constraint 2]
```

## Step 5: Test the Agent

### Test Automatic Delegation

If the description says when to use it, test that trigger:

```
# If description mentions "after code changes"
Review my recent changes

# If description mentions "security"
Check for security issues in the auth module
```

**Expected:** The active host selects this agent when automatic delegation is supported and enabled.
**If failing:** Check discovery, host capabilities, invocation settings, and description clarity. Do not diagnose every failure as missing keywords.

### Test Explicit Invocation

```
Use [agent-name] to [task]
```

**Expected:** Agent performs the task correctly
**If failing:** System prompt needs improvement



### Test Tool Access

```
Use [agent-name] and tell me what tools you have
```

**Expected:** Lists appropriate tools

**If surprising:** Check frontmatter `tools` and `disallowedTools`.


Never perform a destructive operation just to test a restriction. Use harmless tasks and policy inspection.

### Test Edge Cases

```
# Try something outside scope
Use code-reviewer to fix the bug

# Try with missing information
Use code-reviewer  (without specifying what to review)
```

**Expected:** Agent handles gracefully
**If failing:** Add edge case handling to prompt

## Step 6: Check for Anti-Patterns

Review against common anti-patterns:

### Anti-Pattern Checklist

- [ ] **Vague description**: Add specific trigger keywords
- [ ] **Over-broad tools**: Remove unnecessary tool access
- [ ] **No verification**: Add verification steps for writers
- [ ] **No constraints**: Add what NOT to do
- [ ] **Generic naming**: Rename to be task-specific
- [ ] **Missing context**: Add process steps
- [ ] **No output format**: Specify expected output
- [ ] **No error handling**: Add graceful failure behavior

## Step 7: Performance Check

### Token Efficiency

- Does the agent produce unnecessarily verbose output?
- Does it search/read more than needed?
- Is the model appropriate for the task complexity?

### Latency

- Does it take longer than expected?
- Are there unnecessary tool calls?
- Would a faster model work?

### Model Selection


| Task Complexity | Recommended Model |
| --------------- | ----------------- |
| Simple search/grep | `haiku` |
| Code review/analysis | `sonnet` |
| Complex reasoning | `opus` or `inherit` |


## Step 8: Document Improvements

Track what you changed and why:

```markdown
## Agent Audit: [agent-name]
Date: [date]

### Issues Found
1. Description too vague - no trigger keywords
2. Permissions over-privileged for a read-only role
3. No output format specified

### Changes Made
1. Updated description to include "when user mentions review"
2. Applied the native read-only configuration and documented any enforcement gaps
3. Added Output Format section to prompt

### Testing
- Automatic delegation: [Verified in this host, disabled, or unsupported]
- Explicit invocation: Works correctly
- Edge cases: Properly declines to modify files
```

## Audit Checklist Summary

### Native Configuration
- [ ] Name is specific, lowercase, hyphens only
- [ ] Description includes what AND when
- [ ] Description has trigger keywords
- [ ] Tools are minimal necessary
- [ ] Model matches task complexity
- [ ] Actual format matches intended client and location
- [ ] Unsupported fields or enforcement gaps are reported, not silently dropped
- [ ] All existing restrictions are preserved or any explicit migration is approved

### System Prompt
- [ ] Role is clearly defined
- [ ] Process is step-by-step
- [ ] Output format is specified
- [ ] Constraints are defined
- [ ] Edge cases are handled
- [ ] Error handling included

### Testing
- [ ] Automatic delegation tested when supported and enabled
- [ ] Explicit invocation works
- [ ] Tool access is correct
- [ ] Edge cases handled gracefully
- [ ] Performance is acceptable

### Documentation
- [ ] Changes documented
- [ ] Testing verified
- [ ] Team notified if shared agent

## Quick Fixes

### Agent Not Triggering

Add trigger keywords to description:

```yaml
# Before
description: Reviews code

# After
description: Reviews code for quality and security. Use proactively after code changes or when user mentions review, audit, or check code.
```


### Agent Doing Too Much

Add constraints:
```markdown
## Constraints
- Do NOT modify files
- Do NOT run tests
- Focus only on [specific scope]
```

### Inconsistent Output

Add output format:
```markdown
## Output Format

## Summary
[One paragraph]

## Findings
- [Finding 1]
- [Finding 2]
```

### Agent Fails on Edge Cases

Add error handling:
```markdown
## If You Cannot Complete the Task

1. Report what you tried
2. Explain what blocked you
3. Suggest alternatives
4. Do NOT make up information
```

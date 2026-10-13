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

Establish workspace or personal scope using a direct chat question to the user (wait for their reply before continuing) if unspecified. Read the existing file without modifying it. Record its path, intended client, and actual format:

- Markdown with YAML frontmatter: inspect native keys and expected client suffix.
- TOML with `name`, `description`, and `developer_instructions`: Codex custom agent.
- `.md.j2` with canonical `targets`/tools/model tiers: marketplace source, not native configuration.

Cross-check content and extension; do not trust either alone. A Claude file found while using Copilot is not automatically a Copilot agent. **Report mismatched harnesses, unsupported fields, and permission semantics before proposing changes. Never silently convert a format or drop restrictions.** Confirm any migration or overwrite with the user.


Inspect `.codex/agents/*.toml` for project agents or `~/.codex/agents/*.toml` for personal agents. Ask Codex to spawn the exact agent name in a fresh session when needed and verify the intended file loaded.


See [authoring-targets.md](../references/authoring-targets.md) for the separate opt-in source-authoring path.

## Step 2: Review Native Configuration

### Check Required Fields

| Field | Requirement | Common Issues |
| ----- | ----------- | ------------- |
| `name` | Lowercase, hyphens | Spaces, uppercase, special chars |
| `description` | Specific, trigger keywords | Vague, missing "when to use" |

| `developer_instructions` | Complete nonempty string | Missing body, truncated constraints, malformed delimiters |



Parse TOML, not YAML. Require `name`, `description`, and `developer_instructions`. Flag YAML frontmatter, `tools`, `disallowedTools`, `permissionMode`, and copied Claude hooks as unsupported; do not silently remove them. Ensure the parsed instruction string contains the entire intended role.


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
```toml

description = "Reviews code for quality, security, and best practices. Use after code changes or when user mentions review, audit, or code quality."

```

## Step 3: Review Tool Access

### Audit Questions

- [ ] Does the agent need all the tools it has?
- [ ] Is it missing tools it needs?
- [ ] Are write tools appropriate for this agent's purpose?
- [ ] Is command execution necessary, and is it independently constrained?

### Tool Appropriateness Matrix


Reviewers and researchers should set `sandbox_mode = "read-only"` and prohibit modifications in their complete instructions. Writers should inherit an approved session policy. Read-only sandboxing is **not** a substitute for tool allowlists and does not constrain all remote side effects.

If auditing a migrated configuration, explicitly list lost restrictions and whether supported host/service policy can enforce them. Do not report permission equivalence without evidence.


## Step 4: Review Role Instructions


Read the parsed `developer_instructions` value, not just the visible TOML header. Verify safe delimiters and round-trip preservation of headings, code samples, output format, and constraints.


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


Explicitly ask Codex to spawn the agent by name. Do not test it using skill invocation syntax.


### Test Tool Access

```
Use [agent-name] and tell me what tools you have
```

**Expected:** Lists appropriate tools

**If surprising:** Inspect the effective sandbox, network, and remote-tool policies. Codex has no native agent tool allowlist; self-reported tools do not establish read-only enforcement.


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


Prefer omitted model settings (inherit). If the agent pins a model, verify its exact identifier in the active client/account. Test simpler supported models for simple search and more capable supported models for complex reasoning; do not invent model names or use marketplace tiers in native files.


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

Before (configuration fragment):
```toml
description = "Reviews code"
```
After:
```toml
description = "Reviews code for quality and security. Use after code changes or when user mentions review, audit, or check code."
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

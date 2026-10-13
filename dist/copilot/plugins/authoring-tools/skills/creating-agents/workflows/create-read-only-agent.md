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

Ask workspace versus personal scope using a direct chat question to the user (wait for their reply before continuing) if unspecified, then confirm the resolved destination and any overwrite. See [authoring-targets.md](../references/authoring-targets.md).


- **Workspace**: `.github/agents/<name>.agent.md`, shared through version control.
- **Personal**: resolve through the VS Code Chat customization UI on the active profile/host; do not assume a fixed profile path.


## Step 2: Create the File


Create the agent file with YAML frontmatter and Markdown instructions. Explicitly restrict tools to read/search capabilities.


### Minimal Template

````markdown
---
name: your-agent-name
description: What it analyzes. Use when [trigger conditions].
tools: [read, search]
---


You are a [role description].

When invoked:
1. [First step]
2. [Second step]
3. [Output results]

Do NOT modify files, run tests or builds, or change external systems.

````

### Full Example: Code Reviewer


`.github/agents/code-reviewer.agent.md`:


````markdown
---
name: code-reviewer
description: Reviews code for quality, security, and best practices. Use proactively after code changes or when user mentions review, audit, or code quality.
tools: [read, search]

---


You are a senior code reviewer ensuring high standards of quality and security.

When invoked:
1. Identify what to review:
   - If specific files mentioned, focus on those
   - Otherwise, use a diff supplied by the parent or user
   - If neither files nor a diff are supplied, request the review scope; do not assume shell access
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

````

## Step 3: Add Git Access (Optional)

If your reviewer needs `git diff` or `git log`:


Prefer a parent-supplied diff. Adding `execute` enables arbitrary commands, including writes. Do not claim that `[read, search, execute]` is read-only. If command access is indispensable, verify separate host enforcement before broadening tools.


## Step 4: Load the Agent


Open the VS Code Chat agent picker and verify the new agent is listed. Check the chosen personal profile/host or workspace path if it is missing; refresh the chat session if needed.


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

Check automatic delegation only when the active host supports and enables it. A description is a selection hint, not proof that delegation occurred.

### Verify Tool Access

```
Use code-reviewer and tell me what tools you have access to
```


Should expose only `read` and `search`; verify the resolved tool list in the host, not just the agent's self-report.


### Test Edge Cases

```
Use code-reviewer to fix the bug in auth.ts
```

Agent should decline since it's read-only.

## Common Variations

### Security Auditor

Focus the checklist on security concerns:

````markdown
---
name: security-auditor
description: Audits code for security vulnerabilities. Use when user mentions security, audit, vulnerability, or penetration testing.
tools: [read, search]
---


You are a security specialist performing security audits.

Focus areas:
- Authentication and authorization flaws
- Injection vulnerabilities (SQL, command, XSS)
- Secrets exposure
- Insecure dependencies
- Missing input validation

Do NOT modify files, run tests, attempt exploitation, or access external systems. Report findings with evidence and uncertainty.

````

### Performance Analyzer

Focus on performance patterns:

````markdown
---
name: performance-analyzer
description: Analyzes code for performance issues. Use when user mentions performance, speed, optimization, or slow.
tools: [read, search]
---


You are a performance engineer identifying bottlenecks.

Focus areas:
- N+1 query patterns
- Unnecessary iterations
- Memory leaks
- Missing caching opportunities
- Inefficient algorithms

Do NOT modify files or run profilers, tests, or builds. Analyze supplied measurements and code; label unmeasured hypotheses.

````

### Documentation Reviewer

Review documentation quality:

````markdown
---
name: doc-reviewer
description: Reviews documentation for completeness and accuracy. Use when user mentions documentation review or docs audit.
tools: [read, search]
---


You are a technical writer reviewing documentation.

Focus areas:
- Accuracy (does code match docs?)
- Completeness (all features documented?)
- Clarity (understandable by target audience?)
- Examples (working and relevant?)

Do NOT modify files or execute examples. Cross-check against code and report any verification that requires a separate authorized task.

````

## Checklist

Before considering the agent complete:

- [ ] Name is specific and task-focused
- [ ] Description includes trigger keywords
- [ ] Native read-only tool configuration or sandbox is present and limitations are documented
- [ ] System prompt includes clear process
- [ ] Output format is specified
- [ ] Constraints prevent modification
- [ ] Tested with explicit invocation
- [ ] Tested automatic delegation when supported and enabled
- [ ] Verified tool access is correct

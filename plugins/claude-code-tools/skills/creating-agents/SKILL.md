---
name: creating-agents
description: Expert guidance for creating Claude Code subagents and multi-agent workflows. Use when designing new subagents, configuring agent tools/permissions, implementing orchestration patterns, or troubleshooting agent delegation.
---

# Creating Claude Code Agents

Expert guidance for designing and implementing Claude Code subagents based on Anthropic's official specification and industry best practices.

## Core principles

Subagents solve three fundamental problems:

### 1. Context Preservation

Main conversation context is precious. Subagents isolate verbose operations (test runs, documentation fetches, log analysis) and return only summaries.

**Without subagents:** Running tests consumes 50K+ tokens in your main context
**With subagents:** Test output stays in subagent context; you get a 500-token summary

### 2. Parallelization

Launch multiple subagents simultaneously for independent tasks:

```
Research the authentication, database, and API modules in parallel using separate subagents
```

Each explores its area independently, then Claude synthesizes findings.

### 3. Specialization

A single agent handling everything becomes a "jack of all trades, master of none." As instruction complexity increases, reliability decreases. Subagents enable focused expertise with minimal tool access.

## How Delegation Works

Claude automatically delegates based on each subagent's `description` field. Write clear descriptions that include:

- **What it does**: "Reviews code for quality and security"
- **When to use it**: "Use proactively after code changes"
- **Trigger keywords**: Include terms users might say

**Good description:**
```yaml
description: Reviews code for quality, security, and best practices. Use proactively after code changes or when user mentions review, audit, or code quality.
```

**Bad description:**
```yaml
description: Helps with code
```

## Agent Design Principles

### 1. Single Responsibility

Each subagent should excel at ONE specific task. Don't create a "helper" agent that does everything.

**Good:** `code-reviewer`, `test-runner`, `doc-researcher`
**Bad:** `general-helper`, `code-assistant`, `utility-agent`

### 2. Minimal Tool Access

Grant only the tools necessary for the task:

| Role | Recommended Tools |
| ---- | ----------------- |
| Reviewer/Auditor | Read, Grep, Glob |
| Researcher | Read, Grep, Glob, WebFetch, WebSearch |
| Implementer | Read, Write, Edit, Bash, Glob, Grep |
| Domain Expert | Read, Grep, Glob + domain-specific |

See [references/tool-permissions.md](references/tool-permissions.md) for detailed guidance.

### 3. Clear System Prompts

The markdown body becomes the subagent's system prompt. Be specific about:

- When to use which approach
- Output format expectations
- What NOT to do (constraints)

### 4. Model Selection

- **haiku**: Fast, cheap - ideal for read-only exploration
- **sonnet**: Balanced - good for most tasks
- **opus**: Most capable - use for complex reasoning
- **inherit**: Uses main conversation model (default)

## YAML Frontmatter Reference

| Field | Required | Description |
| ----- | -------- | ----------- |
| `name` | Yes | Unique identifier (lowercase, hyphens) |
| `description` | Yes | When Claude should delegate |
| `tools` | No | Tools the agent can use (inherits all if omitted) |
| `disallowedTools` | No | Tools to explicitly deny |
| `model` | No | Model to use (default: inherit) |
| `permissionMode` | No | Permission handling mode |
| `skills` | No | Skills to preload into context |
| `hooks` | No | Lifecycle hooks for this agent |

See [references/official-spec.md](references/official-spec.md) for complete specification.

## Orchestration Patterns

### Fan-Out (Parallel Research)

Multiple agents explore different areas simultaneously:

```
Use subagents to research authentication patterns, database schema, and API design in parallel
```

Best for: Independent research tasks, codebase exploration, documentation gathering.

### Pipeline (Sequential Processing)

Chain agents where each builds on previous results:

```
First use code-reviewer to find issues, then use debugger to fix them
```

Best for: Review-then-fix workflows, multi-stage processing.

### Orchestrator-Worker

A lead agent decomposes tasks and delegates to specialists:

```
Analyze this feature request and delegate implementation to appropriate specialists
```

Best for: Complex features, large-scale refactoring.

See [references/orchestration-patterns.md](references/orchestration-patterns.md) for detailed patterns.

## Common Anti-Patterns

Avoid these mistakes when creating agents:

| Anti-Pattern | Problem | Solution |
| ------------ | ------- | -------- |
| Vague description | Claude doesn't know when to delegate | Include specific trigger keywords |
| Over-broad tools | Security risk, unfocused behavior | Grant minimal necessary permissions |
| No verification | Can't tell if agent succeeded | Include verification steps in prompt |
| Premature complexity | Multi-agent when single suffices | Start simple, add agents as needed |
| Generic naming | Hard to discover and delegate | Use specific, task-focused names |

See [references/anti-patterns.md](references/anti-patterns.md) for detailed guidance.

## What Would You Like To Do?

1. **Create a new agent** - Step-by-step workflow guides
2. **Use a template** - Copy and customize ready-made agents
3. **Audit an existing agent** - Check against best practices
4. **Learn design patterns** - Understand orchestration and anti-patterns

---

### 1. Create a New Agent

Choose by agent type:

- [Read-only agent](workflows/create-read-only-agent.md) - Reviewers, analyzers, auditors
- [Code writer agent](workflows/create-code-writer-agent.md) - Implementers, fixers, generators
- [Research agent](workflows/create-research-agent.md) - Documentation and web researchers

### 2. Use a Template

Ready-to-use agents you can customize:

- [Code reviewer](templates/code-reviewer.md) - Quality and security review
- [Debugger](templates/debugger.md) - Bug diagnosis and fixing
- [Researcher](templates/researcher.md) - Web and documentation research
- [Domain expert](templates/domain-expert.md) - Specialized domain expertise

### 3. Audit an Existing Agent

- [Audit workflow](workflows/audit-existing-agent.md) - Checklist and improvement process

### 4. Learn Design Patterns

- [Orchestration patterns](references/orchestration-patterns.md) - Fan-out, pipeline, orchestrator-worker
- [Tool permissions](references/tool-permissions.md) - Selecting tools by role
- [Anti-patterns](references/anti-patterns.md) - Common mistakes to avoid

## Testing Your Agent

### 1. Manual Testing

```
# Test delegation
Use the [agent-name] to [task description]

# Test automatic delegation (if description says "use proactively")
[Task that should trigger the agent]
```

### 2. Verify Tool Access

Check the agent has exactly the tools it needs, no more:

```
Use [agent-name] to describe what tools you have access to
```

### 3. Test with Different Models

If you set `model: haiku` for speed, ensure instructions are clear enough:

- Haiku needs explicit, step-by-step instructions
- Sonnet/Opus can infer more from context

### 4. Check Edge Cases

- What happens if the agent can't find what it needs?
- Does it fail gracefully or loop indefinitely?
- Are error messages helpful?

## Storage Locations

| Location | Scope | Use Case |
| -------- | ----- | -------- |
| `.claude/agents/` | Current project | Team-shared, version-controlled |
| `~/.claude/agents/` | All your projects | Personal agents |
| `--agents` CLI flag | Current session | Testing, automation |
| Plugin `agents/` | Where plugin enabled | Distributed via plugin |

Higher-priority locations override lower when names conflict.

## Real-World Examples

See [examples/real-world-agents.md](examples/real-world-agents.md) for battle-tested agents including:

- Security auditor
- Performance analyzer
- Documentation generator
- Test writer
- Migration assistant

## Success Criteria

A well-designed agent:

- [ ] Has a **single responsibility** - one job, minimal tools
- [ ] Has a **specific description** with trigger keywords (what AND when)
- [ ] Uses **minimal tool access** appropriate for its role
- [ ] Includes **verification steps** in its system prompt
- [ ] **Handles failures gracefully** with useful error messages
- [ ] Has been **tested** with explicit invocation and automatic delegation

## References

- [Official YAML specification](references/official-spec.md)
- [Orchestration patterns](references/orchestration-patterns.md)
- [Tool permissions by role](references/tool-permissions.md)
- [Anti-patterns to avoid](references/anti-patterns.md)

## Sources

Research for this skill was conducted from multiple authoritative sources:

- [Official Claude Code Docs: Subagents](https://code.claude.com/docs/en/sub-agents)
- [Anthropic Engineering: Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Claude Agent SDK Blog](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)
- [VoltAgent Subagent Collection](https://github.com/VoltAgent/awesome-claude-code-subagents)

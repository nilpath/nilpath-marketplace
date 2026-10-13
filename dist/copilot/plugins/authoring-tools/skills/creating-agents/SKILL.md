---
name: creating-agents
description: Expert guidance for creating custom agents and multi-agent workflows for the active client. Invoke explicitly to design new agents, configure permissions, implement orchestration patterns, or troubleshoot delegation.
disable-model-invocation: true
---

# Creating Custom Agents

Expert guidance for designing custom agents for the active client, with focused responsibilities, explicit permissions, and verifiable results.


Invoke explicitly with `/authoring-tools:creating-agents`. Do not load this skill automatically.


## Authoring Target and Placement

**Default: native output for the active client.** Read [authoring-targets.md](references/authoring-targets.md) before creating or editing an agent.

- Ask whether placement is **workspace** or **personal** using a direct chat question to the user (wait for their reply before continuing) when unspecified.
- Resolve the actual destination before writing; read an existing file and confirm before overwriting it.
- For audits, identify the file's actual format and intended client. Report mismatched harnesses and unsupported configuration; never silently convert or discard restrictions.
- The examples in this skill are native configurations, not marketplace source metadata. Use the separate opt-in source-authoring path only when requested.
- This authoring skill is manual-only. Choose discovery and invocation behavior of the agents it creates independently.

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

Each explores its area independently, then the parent agent synthesizes findings.

### 3. Specialization

A single agent handling everything becomes a "jack of all trades, master of none." As instruction complexity increases, reliability decreases. Subagents enable focused expertise with minimal tool access.

## How Delegation Works


Select a custom agent from the VS Code Chat agent picker, or delegate to it through the agent tool when available. Its `description` helps the parent choose a specialist; description text alone does not guarantee delegation.

Write clear descriptions that include:

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

Grant only the capabilities necessary for the task:


| Role | Native `tools` |
| ---- | -------------- |
| Reviewer/Auditor | `[read, search]` |
| Researcher | `[read, search, web]` |
| Implementer | `[read, search, edit, execute]` |
| Domain Expert | `[read, search]`, add only required capabilities |

Verify aliases against the active host's tool picker. Do not add `execute` merely to obtain diffs: it permits commands that can write.


See [references/tool-permissions.md](references/tool-permissions.md) for detailed guidance.

### 3. Clear System Prompts


The Markdown body supplies the agent's instructions. Be specific about:


- When to use which approach
- Output format expectations
- What NOT to do (constraints)

### 4. Model Selection


Omit `model` to use the current selection. If pinning is needed, select an exact model name supported by the active VS Code model picker. Do not copy Claude aliases or marketplace tiers into native files.


## Native Configuration Reference


Use `.github/agents/<name>.agent.md` with YAML frontmatter and a Markdown body:

| Field | Purpose |
| ----- | ------- |
| `name` | Clear agent name (included in all examples) |
| `description` | What the agent does and when to select it |
| `tools` | Explicit list of active-host tool names/aliases |
| `model` | Optional verified model selection; omitted by default |
| `user-invocable` | Whether it appears for direct user selection |
| `disable-model-invocation` | Whether automatic model invocation is disabled |

Do not copy Claude `permissionMode`, `disallowedTools`, or `skills` into this schema.


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
| Vague description | Parent doesn't know when to delegate | Include specific trigger keywords |
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

Automatic delegation tests apply only when the active host supports and enables it. Inspect the actual selected agent rather than treating a matching answer as proof.

### 2. Verify Tool Access

Check the agent has exactly the tools it needs, no more:

```
Use [agent-name] to describe what tools you have access to
```

### 3. Test with Different Models


Begin with the inherited model. Test any explicitly selected, available model against representative tasks before relying on it. Smaller models often need more explicit process and output instructions.


### 4. Check Edge Cases

- What happens if the agent can't find what it needs?
- Does it fail gracefully or loop indefinitely?
- Are error messages helpful?

## Storage Locations


| Location | Scope |
| -------- | ----- |
| `.github/agents/*.agent.md` | Workspace/team |
| Personal agent location resolved through VS Code's agent customization UI | Personal, active profile/host |

Do not hard-code a local user-profile directory: remote hosts and profiles can use different paths.


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
- [ ] Has been **tested** with explicit invocation and, when supported and enabled, automatic delegation

## References

- [Native configuration specification](references/official-spec.md)
- [Orchestration patterns](references/orchestration-patterns.md)
- [Tool permissions by role](references/tool-permissions.md)
- [Anti-patterns to avoid](references/anti-patterns.md)

## Sources

Research for this skill was conducted from multiple authoritative sources:

- [Official Claude Code Docs: Subagents](https://code.claude.com/docs/en/sub-agents)
- [Anthropic Engineering: Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Claude Agent SDK Blog](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)
- [VoltAgent Subagent Collection](https://github.com/VoltAgent/awesome-claude-code-subagents)
- [VS Code custom agents](https://code.visualstudio.com/docs/agent-customization/custom-agents)
- [Codex subagents](https://developers.openai.com/codex/subagents/)

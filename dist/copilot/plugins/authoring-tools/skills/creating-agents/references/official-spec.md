# Official Subagent Specification

These are **native** agent schemas. For optional marketplace source authoring, see [authoring-targets.md](authoring-targets.md); canonical `targets`, tool names, and model tiers are not native fields.


Reference: [VS Code custom agents](https://code.visualstudio.com/docs/agent-customization/custom-agents).

## File Format

Use `.github/agents/<name>.agent.md` for a workspace agent. Personal agents must be created/opened through VS Code's customization UI to discover the active profile/host location.

```markdown
---
name: code-reviewer
description: Reviews code for quality and security. Use when asked to review changes.
tools: [read, search]
---

You are a code reviewer.

1. Read the supplied diff and relevant files.
2. Report concrete findings with file and line references.
3. If scope is missing, request it rather than assuming shell access.

Do NOT modify files or run commands, tests, or builds.
```

## Configuration Fields

| Field | Guidance |
| ----- | -------- |
| `name` | Included in these examples for clear identification |
| `description` | Explain what the agent does and when to select/delegate to it |
| `tools` | Explicit YAML list of supported tool names or aliases |
| `model` | Optional model or fallback list verified in the active model picker; omit to use current selection |
| `user-invocable` | Controls user selection visibility |
| `disable-model-invocation` | Controls automatic model invocation |

The body after the closing frontmatter marker contains the complete role instructions. There is no `developer_instructions` TOML field in this format.

## Tools and Permission Boundaries

| Alias | Intended capability |
| ----- | ------------------- |
| `read` | Read files |
| `search` | Discover files and search contents |
| `web` | Web research when provided by the host |
| `edit` | Create or change files; add only for writing roles |
| `execute` | Run commands; can write and have external side effects |
| `agent` | Delegate through the host's agent tool when available |

Tool availability varies by host and installed extensions; verify aliases and resolved tools in the active tool picker. Review/research examples deliberately omit `edit` and `execute`. An absent `tools` list does not express read-only intent.

Do not copy Claude `permissionMode`, `disallowedTools`, or `skills` into these files. Hook capabilities are host-specific; do not assume a Claude hook block is portable or silently remove an unsupported restriction.

## Model Guidance

Omit `model` unless the user requests a supported explicit model. Native files do not accept marketplace tiers (`small`, `medium`, `large`, `xlarge`) as a substitute for real model selections. Do not guess names or transplant Claude aliases.

## Loading and Invocation

Select the agent from the VS Code Chat agent picker or ask the parent to delegate to the named custom agent through the agent tool. Check tool availability and invocation settings if delegation fails; a matching `description` is not a guarantee of dispatch.

The command `/authoring-tools:creating-agents` loads this authoring skill. It does not invoke one of the agents you create. No custom agents are registered by this skill.

## Validation

Parse YAML frontmatter, verify path/suffix, inspect the full body, and verify tools/model settings in the active host. Test explicit selection before optional automatic delegation. Report unsupported keys or a mismatched client rather than silently converting a file.

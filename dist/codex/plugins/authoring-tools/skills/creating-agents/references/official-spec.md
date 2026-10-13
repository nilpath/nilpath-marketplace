# Official Subagent Specification

These are **native** agent schemas. For optional marketplace source authoring, see [authoring-targets.md](authoring-targets.md); canonical `targets`, tool names, and model tiers are not native fields.


Reference: [Codex subagents](https://developers.openai.com/codex/subagents/).

## File Format

Use `.codex/agents/<name>.toml` for a project agent or `~/.codex/agents/<name>.toml` for a personal agent.

```toml
name = "code-reviewer"
description = "Reviews code for quality and security. Use when asked to review changes."
sandbox_mode = "read-only"
developer_instructions = '''
You are a code reviewer.

1. Read the supplied diff and relevant files.
2. Report concrete findings with file and line references.
3. If scope is missing, request it.

Do NOT modify files, run tests or builds, or change external systems.
'''
```

## Required Fields

| Field | Purpose |
| ----- | ------- |
| `name` | Unique, task-focused agent identifier |
| `description` | What the role does and when to delegate to it |
| `developer_instructions` | Complete role body including process, output format, constraints, and failure handling |

Do not put the role body after the TOML as bare Markdown. All role instructions must be inside the `developer_instructions` string.

## Optional Settings

| Field | Guidance |
| ----- | -------- |
| `sandbox_mode` | Use `"read-only"` for research, review, and advice |
| `model` | Omit to inherit; otherwise use an ID verified for the installed client/account |
| `model_reasoning_effort` | Omit to inherit; otherwise verify the value is supported by the model |

Writing agents in this skill omit sandbox overrides and inherit session policy. Confirm authorized write/command access; never weaken policy to make a sample work.

## Permissions Are Not Tool Allowlists

Codex native custom-agent TOML has no equivalent to Claude/Copilot `tools` allowlists. Do not add `tools`, `disallowedTools`, `permissionMode`, or Claude hook YAML.

`sandbox_mode = "read-only"` restricts local filesystem writes within the sandbox. It does not imply that all exposed tools are read-only, that network access is absent, or that remote services/databases cannot be modified. Enforce network and remote-service restrictions using the host's policies and service-side authorization. Prompt constraints communicate intent but are not a security boundary.

When migrating an existing allowlist, report this semantic difference explicitly. If equivalent enforcement is required but unavailable, stop the migration rather than dropping restrictions.

## Safe TOML Strings

The guide templates use multiline literal strings delimited by three single quotes. Their current role bodies do not contain that delimiter. Backslashes and nested Markdown fences remain literal. If a customized body contains three single quotes, serialize it using a TOML-compatible escaped basic string instead; escape backslashes, quotes, and control characters. Parse and verify that `developer_instructions` round-trips to the entire intended body. Never truncate or split away constraints to work around a delimiter.

## Loading and Invocation

Ask Codex to spawn the named custom agent as a subagent. If a new file is not discovered, start a fresh session in the intended project and verify the configuration loaded. A description helps selection but does not guarantee automatic delegation.

`$creating-agents` invokes the authoring skill, not a custom agent. The skill-local `agents/openai.yaml` carries `policy.allow_implicit_invocation: false`; it is not a custom-agent registration and is not copied into created agents.

## Validation

Parse TOML and require all three fields above. Check the effective sandbox/model policy in the active client. Test explicit delegation and safe refusal behavior; parser success alone does not prove runtime discovery or enforcement.

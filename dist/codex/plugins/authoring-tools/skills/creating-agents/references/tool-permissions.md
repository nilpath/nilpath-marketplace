# Tool Permissions by Role

Guide for selecting appropriate tools for different agent roles. The principle is **minimal necessary access** - grant only what the task requires.

Configuration snippets below are focused edits, not complete agent files. Use a full role template and the [native specification](official-spec.md) for required fields.


## Quick Reference

| Role | Native configuration | Important limitation |
| ---- | -------------------- | -------------------- |
| Reviewer/auditor/explorer | `sandbox_mode = "read-only"` | Does not remove command or remote tools |
| Researcher | `sandbox_mode = "read-only"` | Web availability/restrictions come from host policy |
| Advisory domain expert | `sandbox_mode = "read-only"` | Return advice; do not apply changes |
| Implementer/bug fixer | Inherit session policy; verify authorized writes | Do not override a restricted session to make a task work |
| Test runner | Inherit approved session policy | Tests often write artifacts; not a read-only role |

## No Native Tool Allowlist

Do not emit `tools`, `disallowedTools`, `permissionMode`, or Claude hooks in Codex agent TOML. Codex sandbox settings and Claude/Copilot allowlists are not equivalent. A migrated allowlist's loss must be reported, not described as identical protection.

## Read-Only Local Work

```toml
sandbox_mode = "read-only"
```

Combine this with complete role instructions prohibiting local changes, unapproved commands, test/build execution, and external changes. The sandbox restricts local writes; the prompt states intent. Neither implies that every exposed remote tool is read-only.

For git review, prefer supplied diffs or permitted read-oriented commands. Never loosen the sandbox when access is denied. Do not infer that all `git` commands are safe: many write, and configurations/aliases can execute external helpers.

## Research and Network Access

Use only web/search tools that the active client makes available under its network and approval policies. An agent TOML sandbox setting does not enable web search or impose a domain allowlist.

For codebase-only research, prohibit external research in `developer_instructions` and enforce no-network requirements through the host. If the enforcement is unavailable, state that limitation rather than promising isolation.

## Writing and Verification

Writer examples omit sandbox overrides to inherit the parent session's policy. Verify permission for both file changes and test/build commands. Report denied operations and incomplete verification honestly. Do not add unrestricted sandbox modes or authorization-bypass instructions.

## Remote Database Work

Read-only local sandboxing does not make SQL read-only. Require database-side read-only credentials/transactions and a vetted query gateway. A keyword denylist misses functions, procedures, and other side effects. Do not expose credentials or perform live queries merely to test an agent configuration.

## Validation

1. Parse native TOML and verify required `name`, `description`, and complete `developer_instructions`.
2. Confirm read-only roles have `sandbox_mode = "read-only"`.
3. Inspect the effective host policy and allowed remote capabilities separately.
4. Exercise safe, bounded tasks and refusal behavior.
5. Report unsupported restrictions and host limitations before any migration.

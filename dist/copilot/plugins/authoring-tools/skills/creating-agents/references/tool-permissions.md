# Tool Permissions by Role

Guide for selecting appropriate tools for different agent roles. The principle is **minimal necessary access** - grant only what the task requires.

Configuration snippets below are focused edits, not complete agent files. Use a full role template and the [native specification](official-spec.md) for required fields.


## Quick Reference

| Role | Native `tools` | Boundary |
| ---- | -------------- | -------- |
| Reviewer/auditor/explorer | `[read, search]` | No editing or general commands |
| Researcher | `[read, search, web]` | Web destinations still need host policy |
| Implementer/bug fixer | `[read, search, edit, execute]` | Writes and verification commands are intentional |
| Test runner | `[read, search, execute]` | Tests and commands may write artifacts |
| Documentation writer | `[read, search, edit]` | Parent must run any executable validation |

These are active-host tool aliases, not marketplace canonical names. Confirm them in VS Code's tool picker and inspect their resolved capabilities. Installed tools and host policies can differ.

## Read-Only Roles

```yaml
tools: [read, search]
```

Use for review, auditing, and code analysis. Return recommendations instead of applying changes. Ask the parent/user for a diff when no dedicated approved diff tool is available. Do not add `execute` merely because the prompt says “run git diff.”

## Research Roles

```yaml
tools: [read, search, web]
```

Web access does not mean arbitrary external actions are permitted. Require source attribution, bounded searches, no local modifications, and no execution of downloaded examples. If the host lacks web tools, report unavailable access.

## Writing and Verification Roles

```yaml
tools: [read, search, edit, execute]
```

`edit` changes files. `execute` can also write files, modify repositories, contact services, or run programs with side effects. Scope the task and host permissions before granting it. A test runner with no `edit` tool is still not read-only.

## Inheritance Versus Explicit Tools

An omitted `tools` list does not establish a restricted agent. Use explicit lists for bounded roles and verify effective access in the host. Do not substitute Claude `disallowedTools`, `permissionMode`, or hook blocks for native enforcement.

## Nuanced Restrictions

- **Git access**: use a supplied diff by default. If command execution is required, use supported host enforcement and tested command validation; a “git only” prompt is not enforcement.
- **Database reads**: require a vetted gateway with read-only credentials and bounded queries. `execute` plus a keyword filter cannot establish database safety.
- **Network restrictions**: use host/network policy for destination restrictions. `web` itself is not a domain allowlist.
- **Delegation**: add the `agent` tool only for an intentional orchestrator supported by the active host, not every worker.

## Verification Checklist

1. Start with read/search only; justify each added capability.
2. Inspect resolved tools in the active host.
3. Test expected access and safe refusal without attempting destructive operations.
4. Document prompt intent separately from enforced controls.
5. If a required restriction cannot be represented/enforced, report it instead of silently broadening access.

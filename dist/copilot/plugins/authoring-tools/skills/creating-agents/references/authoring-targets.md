# Authoring Target and Placement

## Default: Native Agent for the Active Client

Use a direct chat question to the user (wait for their reply before continuing) to establish workspace versus personal scope when unspecified. Confirm the destination and any overwrite before writing; inspect existing files first.


- Workspace: `.github/agents/<name>.agent.md`.
- Personal: use VS Code's Chat customization UI to create/open a personal custom agent and resolve the active profile/host location. Do not assume a fixed operating-system profile directory.
- Use YAML frontmatter and the complete Markdown role instructions.
- Select the agent in the Chat agent picker, or delegate through the agent tool when the host supports it and the agent is available.
- Keep examples' `read`, `search`, and `web` aliases read-only. Add `edit` for writing and `execute` only when commands are required. Verify available tools in the host's tool picker.


## Audit Before Editing

Identify the actual format from content as well as extension: Markdown/YAML, Codex TOML, or marketplace `.j2` source. Record the intended harness, scope, model settings, and permission controls. Report unsupported keys and mismatched harnesses. Do not silently convert a file, discard tool restrictions, or replace an enforced restriction with prompt prose. Obtain approval for any explicit migration.

## Optional: nilpath-marketplace Source Authoring

Only take this path when the user explicitly asks for a marketplace component. It is separate from native authoring; the schema below is **source-only**, not a native agent configuration.

Create `src/plugins/<plugin>/agents/<category>/<name>.md.j2` with canonical metadata and shared role instructions. Never hand-edit `dist/` or generated registries.

```yaml
name: code-reviewer
description: Reviews code for quality and security. Use when asked to review changes.
targets: [claude, copilot, codex]
tools: [file-read, content-search, glob-search]
model: medium
permissionMode: plan
```

Use canonical tools from `src/harnesses/tools.yaml`, ordered model tiers (`small`, `medium`, `large`, `xlarge`), and Jinja harness branches/prose helpers. Consult the repository's existing maps; do not expand global schemas to accommodate an example's optional native feature.

The builder maps agent entrypoint metadata, but does **not** translate fenced frontmatter in supporting guides. Those examples need explicit harness branches. Loss of a tool allowlist when targeting Codex is not equivalent to the read-only sandbox translation: review both the emitted configuration and its limitations.

Build and validate every requested target after source changes. This skill's `agents/openai.yaml` is skill-local Codex invocation-policy metadata, **not** a custom agent registration. The authoring-tools plugin contains two skills and zero plugin agents.

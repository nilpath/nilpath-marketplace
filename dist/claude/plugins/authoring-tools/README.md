# authoring-tools

Guidance for authoring native skills and agents for **Claude Code**, **GitHub Copilot in VS Code**, and **Codex**. Shared workflows render with the active harness's formats, locations, invocation controls, and examples.

Version: **0.9.0**

## Skills

Both skills target all three harnesses and require explicit invocation. Claude and Copilot use `disable-model-invocation: true`; Codex uses skill-local `agents/openai.yaml` metadata with `policy.allow_implicit_invocation: false`. These controls apply to the authoring tools themselves, not automatically to every skill they create.

| Skill | Claude / Copilot VS Code plugin command | Codex command | Purpose |
| --- | --- | --- | --- |
| creating-skills | `/authoring-tools:creating-skills` | `$creating-skills` | Create, refine, and audit native skills and their supporting resources |
| creating-agents | `/authoring-tools:creating-agents` | `$creating-agents` | Design, configure, and audit native custom agents and delegation workflows |

Standalone Copilot skills use `/creating-skills` and `/creating-agents`; installed plugin skills use the plugin prefix. Keep the skill's `name` field unprefixed in either case.

## Native output

The default is to create files for the active harness. Choose project or personal scope before writing, follow existing project conventions, and confirm before overwriting an existing file.

| Harness | Project skills | Project agents |
| --- | --- | --- |
| Claude Code | `.claude/skills/<name>/SKILL.md` | `.claude/agents/<name>.md` |
| Copilot VS Code | `.github/skills/<name>/SKILL.md` or `.agents/skills/<name>/SKILL.md` | `.github/agents/<name>.agent.md` |
| Codex | `.agents/skills/<name>/SKILL.md` | `.codex/agents/<name>.toml` |

Skills share the [Agent Skills format](https://agentskills.io/specification), but optional metadata and runtime behavior differ. Agent definitions are not interchangeable: Claude and Copilot use Markdown with YAML frontmatter; Codex uses TOML with `name`, `description`, and `developer_instructions`. A Codex read-only sandbox is not a tool allowlist.

Codex's skill-local `agents/openai.yaml` controls skill metadata and invocation policy; it is not a custom-agent definition. This plugin contains two skills and no standalone agents.

## Marketplace source authoring

When explicitly contributing to this marketplace instead of creating a native local customization, author under `src/plugins/`, use canonical metadata and `.j2` templates, and run `make build`. Do not put build-only `targets`, canonical tool/model identifiers, or unrendered Jinja into native client files.

## Client limitations

- Copilot VS Code is the supported authoring target. The shared Copilot distribution retains manual-only flags for CLI users, but CLI versions may have explicit-invocation issues; do not remove the flags to work around them.
- Codex plugins are supported in the CLI and desktop app, not the IDE extension. Local skills and custom agents are a separate authoring/discovery mechanism.
- Discover available models, tools, and personal-agent locations in the active client rather than assuming another harness's identifiers or VS Code profile layout.

See the official [VS Code skills](https://code.visualstudio.com/docs/agent-customization/agent-skills), [VS Code agents](https://code.visualstudio.com/docs/agent-customization/custom-agents), [Codex skills](https://developers.openai.com/codex/skills/), and [Codex subagents](https://developers.openai.com/codex/subagents/) documentation.

> Generated from this repo's `src/plugins/authoring-tools/` sources — edit there, not in `dist/`.

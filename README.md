# nilpath-marketplace

A marketplace for my AI coding-agent extensions — skills and agents authored once, distributed to **Claude Code**, **GitHub Copilot (VS Code)**, and **Codex**. Inspired by [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin).

## Install

**Claude Code** (all 15 skills + 12 agents):

```bash
/plugin marketplace add nilpath/nilpath-marketplace
/plugin install claude-code-tools
```

**GitHub Copilot (VS Code)** (8 portable skills): add this repo as a plugin marketplace in your settings:

```json
"chat.plugins.marketplaces": ["nilpath/nilpath-marketplace"]
```

then install `claude-code-tools` from the Extensions view (`@agentPlugins`). Alternatively, copy any folder from `plugins/claude-code-tools/skills-portable/` into your repo's `.github/skills/`.

**Codex** (8 portable skills):

```bash
codex plugin marketplace add git@github.com:nilpath/nilpath-marketplace.git
codex plugin install claude-code-tools
```

Skills are also discoverable via the `.well-known/skills/` index.

## Portability

| Component | Claude Code | Copilot | Codex |
| --- | --- | --- | --- |
| creating-mermaid-diagrams, engineering-principles, gh-address-comments, gh-pr-review, git-advanced, git-commits, git-stacked-prs, using-git-worktrees | ✅ | ✅ | ✅ |
| creating-agents, creating-skills, executing-plan, performing-code-review, planning, researching, writing-documentation | ✅ | — | — |
| all 12 agents | ✅ | — | — |

The Claude-only skills orchestrate Claude Code subagents (TodoWrite, AskUserQuestion, `Agent(...)`) or document Claude Code's own formats, so they are exempted from the other targets.

## How it works

Everything under `plugins/`, `.claude-plugin/`, `.agents/`, and `.well-known/` is **generated** — do not edit it directly. The single source of truth is `src/`:

```text
src/
├── harnesses/          # per-harness config: tool-name maps, model tiers, frontmatter schemas
├── skills/<name>/      # SKILL.md.j2 + references/ templates/ workflows/ scripts/
├── agents/<cat>/       # <name>.md.j2
└── plugin.yaml         # plugin + marketplace metadata, version, MCP servers
```

Sources use a harness-neutral vocabulary — canonical tool names (`shell(git:*)`, `file-read`, `subagent(x)`), model tiers (`small`–`xlarge`), and reasoning levels (`minimal`–`max`) — which `tools/buildkit` translates per harness.

## Development

```bash
make install          # venv + deps + buildkit
make build            # render src/ -> all harness outputs
make check            # fail if committed output drifts from src/ (CI gate)
make test-static      # structure tests over the generated output
```

Workflow: edit `src/`, run `make build`, commit sources **and** generated output together. See [ai_docs/release-workflow.md](ai_docs/release-workflow.md) for releases.

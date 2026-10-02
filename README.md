# nilpath-marketplace

A marketplace for my AI coding-agent extensions — skills and agents authored once under `src/`, built into per-harness distributions for **Claude Code**, **GitHub Copilot (VS Code)**, and **Codex**. Inspired by [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin).

## Plugins

| Plugin | Contents | Claude Code | Copilot | Codex |
| --- | --- | --- | --- | --- |
| **git-tools** | 6 git/gh workflow skills | ✅ | ✅ | ✅ |
| **engineering-workflow** | research→plan→implement→review pipeline: 5 skills, 10 agents, context7 MCP | ✅ | ✅¹ | ✅¹ |
| **documentation** | writing-documentation + mermaid skills, doc-writer/doc-auditor agents | ✅ | ✅¹ | ✅¹ |
| **authoring-tools** | creating-skills, creating-agents (about Claude Code's own formats) | ✅ | — | — |

¹ The orchestrator skills (researching, planning, executing-plan, performing-code-review, writing-documentation) are adapted per harness: subagent dispatch, todo tracking, and user questions render in each harness's native mechanism. They degrade gracefully on Copilot/Codex (chat questions instead of structured question UI, no parallel exploration fan-out).

Dependencies: `engineering-workflow` uses skills from `git-tools` and the doc-writer agent from `documentation` — install them together.

## Install

**Claude Code:**

```bash
/plugin marketplace add nilpath/nilpath-marketplace
/plugin install git-tools          # or engineering-workflow, documentation, authoring-tools
```

**GitHub Copilot (VS Code):** add the repo as a plugin marketplace in settings, then install from the Extensions view (`@agentPlugins`):

```json
"chat.plugins.marketplaces": ["nilpath/nilpath-marketplace"]
```

Alternatively, copy any skill folder from `dist/copilot/plugins/<plugin>/skills/` into your repo's `.github/skills/`.

**Codex:**

```bash
codex plugin marketplace add git@github.com:nilpath/nilpath-marketplace.git
codex plugin install git-tools
```

## How it works

Everything under `dist/`, plus the three root registry files (`.claude-plugin/marketplace.json` for Claude Code, `.github/plugin/marketplace.json` for VS Code Copilot, `.agents/plugins/marketplace.json` for Codex), is **generated** — never edit it. The single source of truth is `src/`:

```text
src/
├── harnesses/                  # per-harness config: tool-name maps, model tiers, schemas
├── marketplace.yaml            # marketplace metadata + shared plugin defaults
└── plugins/<plugin>/
    ├── plugin.yaml             # name, version, description, optional MCP servers
    ├── README.md               # copied into every harness tree
    ├── skills/<name>/          # SKILL.md.j2 + references/ templates/ scripts/
    └── agents/<cat>/<name>.md.j2

dist/
├── claude/plugins/<plugin>/    # Claude plugin trees (.claude-plugin/, skills/, agents/)
├── copilot/plugins/<plugin>/   # Agent Plugins 1.0 trees (plugin.json, skills/, com.github.copilot/agents/)
└── codex/plugins/<plugin>/     # Codex plugin trees (.codex-plugin/, skills/, agents/*.toml)
```

Sources use a harness-neutral vocabulary — canonical tool names (`shell(git:*)`, `file-read`, `subagent(x)`), model tiers (`small`–`xlarge`), and reasoning levels (`minimal`–`max`) — which `tools/buildkit` translates per harness.

## Development

```bash
make install          # venv + deps + buildkit
make build            # render src/ -> dist/ (all harnesses)
make check            # fail if committed output drifts from src/ (CI gate)
make test-static      # structure tests over the generated output
```

Workflow: edit `src/`, run `make build`, commit sources **and** `dist/` together. See [ai_docs/release-workflow.md](ai_docs/release-workflow.md) for releases.

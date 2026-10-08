# nilpath-marketplace

A marketplace for my AI coding-agent extensions — skills and agents authored once under `src/`, built into per-harness distributions for **Claude Code**, **GitHub Copilot (VS Code and CLI)**, and **Codex**. Inspired by [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin).

## Plugins

| Plugin | Contents | Claude Code | Copilot | Codex |
| --- | --- | --- | --- | --- |
| **git-tools** | 6 git/gh workflow skills | ✅ | ✅ | ✅ |
| **engineering-workflow** | research→plan→implement→review pipeline: 5 skills, 10 agents, context7 MCP | ✅ | ✅¹ | ✅¹ |
| **documentation** | writing-documentation + mermaid skills, doc-writer/doc-auditor agents | ✅ | ✅¹ | ✅¹ |
| **authoring-tools** | creating-skills, creating-agents (about Claude Code's own formats) | ✅ | — | — |

¹ The orchestrator skills (researching, planning, executing-plan, performing-code-review, writing-documentation) are adapted per harness: subagent dispatch, todo tracking, and user questions render in each harness's native mechanism. They degrade gracefully on Copilot/Codex (chat questions instead of structured question UI, no parallel exploration fan-out).

Dependencies: `engineering-workflow` uses skills from `git-tools` and the doc-writer agent from `documentation` — install them together.

## Manual-only skills

Four selected skills require explicit user invocation; they must not be loaded automatically by the model or another workflow:

| Skill | Claude Code | Copilot (VS Code and CLI) | Codex |
| --- | --- | --- | --- |
| `researching` | `/engineering-workflow:researching` | `/researching` | `$researching` |
| `planning` | `/engineering-workflow:planning` | `/planning` | `$planning` |
| `creating-skills` | `/authoring-tools:creating-skills` | Not distributed | Not distributed |
| `creating-agents` | `/authoring-tools:creating-agents` | Not distributed | Not distributed |

`creating-skills` and `creating-agents` remain Claude-only because they teach Claude Code's own authoring formats. `researching` and `planning` ship in all three distributions. Claude and Copilot enforce manual-only selection with `disable-model-invocation: true` in skill frontmatter; Codex uses `policy.allow_implicit_invocation: false` in each skill's `agents/openai.yaml` sidecar.

After the design specification is approved and committed, `researching` shows the user the planning command with the actual feature path, then stops. The user must invoke planning explicitly; researching never invokes it automatically.

**Enforcement takes priority over compatibility.** Copilot VS Code and Copilot CLI use the same generated Copilot output and retain the manual-only flag. CLI runtime support for these flagged skills is not guaranteed: open issues [github/copilot-cli#4438](https://github.com/github/copilot-cli/issues/4438) and [github/copilot-cli#4637](https://github.com/github/copilot-cli/issues/4637) report inconsistent explicit invocation and `Skill not found` errors, including a slash-command path that can load instructions while another lookup reports failure. Do not remove the flag or switch to the Claude distribution as a workaround.

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

**GitHub Copilot CLI:** register the same marketplace and install the shared Copilot plugins:

```bash
copilot plugin marketplace add nilpath/nilpath-marketplace
copilot plugin install git-tools@nilpath-marketplace
copilot plugin install documentation@nilpath-marketplace
copilot plugin install engineering-workflow@nilpath-marketplace
```

Both Copilot clients use `.github/plugin/marketplace.json`, which points to `dist/copilot/plugins/<plugin>/`; there is no separate CLI build. The [official CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference) documents support for this registry location and Agent Plugins 1.0 manifests. The [official CLI skills guide](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills) documents explicit `/skill-name` requests. Installation-format support does not guarantee runtime invocation of the manual-only skills; see the caveat above.

**Codex:**

```bash
codex plugin marketplace add git@github.com:nilpath/nilpath-marketplace.git
codex plugin install git-tools
```

## How it works

Everything under `dist/`, plus the three root registry files (`.claude-plugin/marketplace.json` for Claude Code, `.github/plugin/marketplace.json` for Copilot VS Code and CLI, `.agents/plugins/marketplace.json` for Codex), is **generated** — never edit it. The single source of truth is `src/`:

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

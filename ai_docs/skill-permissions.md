# Skill permissions

Supported clients are Claude Code, Copilot CLI, and Codex. Native Copilot use
inside VS Code is unsupported. Copilot CLI in a VS Code terminal remains CLI use.

## Authoring and translation

Canonical `tools` remain the only source declaration. `ToolEntry` represents
both plain and scoped tools. Agent tools describe availability. Skill tools
describe approvals, not an exhaustive list of tools the model can use.

| Client | Agent tools | Skill approvals |
| --- | --- | --- |
| Claude Code | Existing native tool names | Scoped `Bash(...)` rules in `allowed-tools` |
| Copilot CLI | Existing aliases such as `execute`, `read`, `edit`, `search`, `agent`, and `web` | Emission disabled |
| Codex | Existing agent sandbox configuration | Canonical skill tools stripped |

`HarnessConfig.tool_policy(kind)` selects the complete `frontmatter.<kind>.tools`
policy when present. Otherwise it selects the top-level `tools` policy.
The policies do not merge. Translation and serialization use the same component
kind, so an agent alias cannot become a skill approval by inheritance.

Copilot's dormant skill policy preserves scopes and serializes a YAML list.
It maps canonical shell to `shell`, not `execute`. `scoped_only: [shell]`
drops bare shell with a diagnostic. Unsupported canonical tools produce
diagnostics. Unknown tools and malformed or empty scopes fail the build.
An empty Codex map continues to strip valid declarations without warnings.
Relative paths and scopes containing slashes are not rejected globally.

The Copilot skill schema does not accept raw `allowed-tools`. Canonical `tools`
are translated and validated, but `key_for_tools: null` keeps the translated
field out of generated skills. Changing that key alone is not an approved
activation path. The interpreter and installed-path failures below remain
blocking evidence.

## Script declarations

Direct executable and interpreter-prefixed commands require different rules.
The rule must match the command the skill actually invokes.

```jinja
tools:
  - "shell(gh:*)"
{% if harness == "claude" %}
  - 'shell("{{ skill_root }}/scripts/helper.sh":*)'
  - 'shell(python3 "{{ skill_root }}/scripts/helper.py":*)'
{% endif %}
```

Claude renders `skill_root` as `${CLAUDE_PLUGIN_ROOT}/skills/<skill-name>`.
The quotes protect installation paths with spaces. Scripts retain the
repository working directory.

Run the helpers directly and read their JSON from the tool result. Claude's
command-substitution fixture is denied with a static-analysis diagnostic.
Its pipeline fixture succeeds. A script-path rule does not promise approval
for every shell composition that contains that path.

The GitHub and stacked-PR skills and the nstack logger use installed absolute
paths. On Copilot CLI and Codex their command examples contain an explicit
skill-directory placeholder. Resolve it from the loaded skill's location and
replace it in each command. It is not a client variable and does not expand
automatically. A relative `./scripts/...` path from the repository is not an
installed skill path. Ordinary manual script approval remains in effect.

`nstack-flow` and `setup-nstack` keep their existing broad Claude shell grants
because they orchestrate general shell work. Adding a narrow publisher grant
beside unrestricted shell would not narrow it. The publisher runs with
`python3` and a quoted script path. `setup-nstack` resolves its Python helper
under plugin hooks, not under the skill directory. Plugin hooks execute
independently of skill frontmatter.

## Permission-enforced local observations

The local verifier exercised Claude Code 2.1.250 and Copilot CLI 1.0.101.
Claude checks explicitly activated the fixture with a slash command in
permission-enforced print mode. They did not verify model-initiated Skill-tool
activation or the Claude interactive UI. Unapproved interpreter and portable-root
calls prompted in Copilot interactive mode. The verifier did not accept those
prompts. Headless calls were denied. The verifier did not test Codex runtime
approvals, marketplace installation or discovery, or subagent inheritance.

It loaded generated harmless plugin fixtures with `--plugin-dir`, in paths
with spaces, from separate disposable working directories. This is not a
marketplace-installation or paid-model integration test.

| Case | Claude print mode | Copilot interactive | Copilot headless |
| --- | --- | --- | --- |
| No-grant baseline | Denied | Command approval prompt | Denied |
| Quoted direct script with exact absolute rule | Executed | Executed with fixture-path access | Denied |
| Different script under that rule | Denied | Command approval prompt | Denied |
| `python3` plus quoted script path | Executed | Command approval prompt | Denied |
| Different Python script or inline Python under that rule | Denied | Command approval prompt | Denied |
| Explicit deny beside the direct grant | Denied | Denied | Denied |
| Different working directory | Executed | Executed with fixture-path access | Denied |
| Portable plugin-root variable in the rule | Executed | Command approval prompt | Denied |

Copilot's direct-script success requires separate path access. Without
`--add-dir` for the fixture plugin directory, interactive mode asks for path
access even when the shell rule matches. Tool, filesystem-path, and URL
permissions are distinct checks. The verifier also sends `curl` only to a
loopback fixture endpoint. Copilot's offline mode stays enabled, so these
results do not establish general network-access behavior.

The portable-path fixture probes `${CLAUDE_PLUGIN_ROOT}`, the variable already
used by this repository's plugin hooks on both clients. A hook variable does
not establish skill-frontmatter substitution. There is no verified portable
Copilot script-root substitution. No hardcoded home directory or blanket
shell grant replaces it.

The Claude multi-turn fixture executes the helper in the invoking turn and
denies it in the next user turn without another skill invocation. Copilot
executes it again in the next user turn without another skill invocation.
Copilot skill grants must not be described as per-skill isolation.
Subagent inheritance is unverified. The verifier does not spawn subagents.

## Deferred callers

`performing-code-review`, `researching`, and `creating-mermaid-diagrams` have
pre-existing tool callers that this change does not convert. They remain a
follow-up scope. This change does not normalize those callers.

## Rerun the observations

The verifier uses Python's standard library, a Unix PTY for interactive mode,
and the real client executables.
It creates fresh `HOME` and client configuration directories. Copilot runs in
offline mode with built-in MCP servers and unrelated instructions disabled.
Claude runs with `--bare`, empty setting sources, strict empty MCP
configuration, a local dummy API key, and ordinary permission checks.
The deterministic providers bind only to `127.0.0.1`.
No user credentials or project content enter the fixture sessions.

Run each client and mode independently. Choose an artifact directory outside
the checkout.

```bash
python3 tools/verify_skill_permissions.py --client claude --output-dir /tmp/permissions-claude
python3 tools/verify_skill_permissions.py --client copilot --output-dir /tmp/permissions-copilot-headless
python3 tools/verify_skill_permissions.py --client copilot --interactive --output-dir /tmp/permissions-copilot-interactive
```

`--case` selects individual cases and can be repeated. Each case saves the
exact command, CLI version, scoped rule, tool results, transcript, and observed
fixture effects. Successful helpers also report their actual working directory.
`summary.json` records the observations. Exit zero means
the observations are conclusive, not that approval activation is safe.
An inconclusive case fails the verifier. It never accepts a tool, path, or URL
approval prompt. The interactive driver accepts only temporary folder trust.

`tests/behavioral/runner.py` uses `bypassPermissions`. Those tests establish
workflow behavior, not permission enforcement.

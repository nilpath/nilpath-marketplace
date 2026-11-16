# Model configuration and hook helper

[Script](../../../com.github.copilot/hooks/nstack_config.py).
Inspect or change the current client's role models and record dispatch evidence.
The same file implements the plugin's automatic launch and session-start hooks.
Requires Python 3.11+, standard library only.

## Installed path

Use the helper from this client's installed plugin, not the source checkout or
a different installed version. It discovers its client from the neighboring
plugin manifest. It lives under plugin hooks, not this skill's scripts.


`<helper>` is the absolute path to `../../com.github.copilot/hooks/nstack_config.py`,
resolved from the installed setup-nstack directory.


Replace `<helper>` in each command with that absolute path. Quote it and keep
the repository working directory. `--help` and subcommand `--help` own the
exact argument schema.

## Administrative commands

| Command | Result or effect |
| --- | --- |
| `python3 "<helper>" roles` | Role catalog, built-in defaults, supported efforts and configuration path |
| `python3 "<helper>" status` | Effective model/effort, source and verification per role/seat |
| `python3 "<helper>" configure --input <choices.json> --dry-run` | Preview changes and return `plan_id`, without writing |
| `python3 "<helper>" configure --input <choices.json> --apply --plan-id <plan_id>` | Apply the exact confirmed preview |
| `python3 "<helper>" record-verification --role <role> --seat <n> --status <verified-or-failed> --evidence "<observation>"` | Save evidence for the current model/effort at that seat |

Overrides live in `~/.nstack/models.json`, separately for each client.
Never hand-write that file. An input replaces this client's overrides as a
whole, so include all roles that should differ from defaults. Empty `roles`
clears them. Other clients are preserved.

```json
{
  "schema_version": 1,
  "clients": {
    "copilot": {
      "roles": {
        "review-panel-reviewer": [{"model": "<model-a>", "effort": "high"}, {"model": "<model-b>", "effort": "high"}]
      }
    }
  }
}
```

Write choices to a temporary file outside the repository. Preview first, show
the changes to the user, and apply only after confirmation. A stale plan exits
5 with `stale_plan`; preview again and get fresh confirmation. Remove only the
temporary input afterward.

Commands print JSON on stdout. Exit 0 means `ok: true`; classified failures
return a nonzero exit and `errors` containing `code`, `message` and `repair`.
Invalid CLI usage exits 2. Stop on errors rather than guessing defaults or
claiming a change applied. No-op configuration changes write nothing.

## Automatic hooks and verification

The host invokes `hook` with a launch payload on stdin and `session-start`
with its session payload. They emit client-specific hook JSON, not the
administrative result format. Untagged launches pass through; tagged launches
use the configured role/seat and append required-read guidance.

Hook execution is independent of skill frontmatter approvals. Hooks step aside
on unsupported Python or unexpected hook failures; a missing verified hook
footer still blocks nstack delegates under their own instructions.
Do not invoke these entrypoints as substitutes for host dispatch.

[Setup nstack](../SKILL.md) owns model choice, probe ordering and user reporting.
A configuration or subagent self-report is not execution evidence. Record
`verified` only when the client identifies the model that actually served the
probe; otherwise leave it unverified or record an observed failure.

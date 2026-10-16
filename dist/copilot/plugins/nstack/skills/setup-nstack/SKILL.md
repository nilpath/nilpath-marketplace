---
name: setup-nstack
description: Reviews and changes which model and reasoning effort nstack uses for each delegated role (how/why explorers and synthesizers, swarm workers, candidate-graft and architect runners, review-panel reviewers, and the implementer, hardest-task, and judgment tiers), then checks that the client actually runs them. Optional; nstack works on built-in defaults. Invoke explicitly to inspect or change nstack models.
disable-model-invocation: true
---

# Setup nstack

Review and change the model and effort nstack uses for each delegated role in this client, then check the client runs them. Every role has a built-in default, so this is optional.

nstack's plugin hook reads the `[nstack role=<role> seat=<n>]` tag on each launch of `nstack-agent`, sets the role's model and effort, and routes read-only roles to `nstack-reader`. At session start it adds an `nstack panels` line with each panel's seats. Overrides live in `~/.nstack/models.json`, per client. Model changes apply to the next launch, seat counts to new sessions.

Never hand-write `models.json`. Use the hook's script, `<helper>`: `../../com.github.copilot/hooks/nstack_config.py` from this skill's base directory (absolute path). It needs Python 3.11 or newer.

Open a todolist with one entry per step before starting.

## 1. Load the current state

Run `python3 --version`, then `python3 <helper> roles` (catalog, defaults, effort levels) and `python3 <helper> status` (effective model, effort, source, and verification per seat). Stop on Python below 3.11, or on `"ok": false` and show its `message` and `repair`.

## 2. Choose overrides

Show a table of every role with its model, effort, and source. Ask which to change with a direct chat question to the user (wait for their reply before continuing).

Use model ids as Copilot lists them (`claude-opus-5.5`, `gpt-6.1-sol`), or `inherit`. They work in Copilot CLI and VS Code Agent Host alike. Effort is `low`, `medium`, `high`, `xhigh`, or `max`, where the model supports it. Never set a model the user hasn't confirmed they can use.

Panel roles take 2 to 6 seats (`candidate-graft-judge` 1 to 6). Repeating a model across seats gives independent attempts, not model diversity. Say so.

## 3. Preview

Write the overrides to a temp JSON file outside the repository. It replaces this client's overrides as a whole, so list every role that should differ from its default. Empty `roles` clears them.

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

Run `python3 <helper> configure --input <overrides.json> --dry-run` and show each changed role's `before` and `after`. Fix validation errors with the user and preview again.

## 4. Apply

After the user confirms, run `python3 <helper> configure --input <overrides.json> --apply --plan-id <plan_id>`. On `stale_plan` (exit 5), preview again and get fresh confirmation. Delete the temp file.

## 5. Check dispatch

A configured model is not proof the client runs it. Probe at least one seat per distinct model with the task tool with agent type `nstack:nstack-agent`, `[nstack role=<role> seat=<n>]` at the start of the description, and the brief as the prompt and this brief:

```text
[nstack role=<role> seat=<n>] This is an nstack setup probe. Do not read, write, or run anything.
Reply with exactly one line: NSTACK-PROBE <role> <seat>
```

Record the result with `python3 <helper> record-verification --role <role> --seat <n> --status <verified|failed> --evidence "<observation>"`. Record `failed` when the launch is blocked or the model is rejected, and show the error. Record `verified` only when the client shows which model served the launch (the subagent's model in the session log or timeline), and quote it. A subagent's claim about its own model is not evidence. Otherwise leave the seat unverified.

## 6. Report

The overrides applied (or defaults in use), the effective model and effort per role from `status`, each probed seat as verified, failed, or unverified with the reason, and anything still blocked. Re-running is safe; unchanged choices write nothing.

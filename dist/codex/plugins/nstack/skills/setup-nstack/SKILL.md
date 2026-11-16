---
name: setup-nstack
description: Reviews and changes which model and reasoning effort nstack uses for each delegated role (how/why explorers and synthesizers, swarm workers, candidate-graft and architect runners, review-panel reviewers, and the implementer, hardest-task, and judgment tiers), then checks that the client actually runs them. Optional; nstack works on built-in defaults. Invoke explicitly to inspect or change nstack models.
---

# Setup nstack

Review and change the model and effort nstack uses for each delegated role in this client, then check the client runs them. Every role has a built-in default, so this is optional.

nstack's plugin hook reads the `[nstack role=<role> seat=<n>]` tag on each launch of `nstack-agent`, sets the role's model and effort, and routes read-only roles to `nstack-reader`. At session start it adds an `nstack panels` line with each panel's seats. Overrides live in `~/.nstack/models.json`, per client. Model changes apply to the next launch, seat counts to new sessions.

Read the [configuration helper reference](references/nstack-config.md) for its installed path, input format and result handling. Use its `<helper>` path in the steps below. Never hand-write `models.json`.

Open a todolist with one entry per step before starting.

## 1. Load the current state

Run `python3 --version`, then `python3 "<helper>" roles` (catalog, defaults, effort levels) and `python3 "<helper>" status` (effective model, effort, source, and verification per seat). Stop on Python below 3.11, or on `"ok": false` and show its `message` and `repair`.

Codex runs plugin hooks only once trusted. If nstack's hook is untrusted, have the user trust it in `/hooks` first. Until then nstack agents reply that the hook did not run.

## 2. Choose overrides

Show a table of every role with its model, effort, and source. Ask which to change with a direct chat question to the user (wait for their reply before continuing).

Use model ids from the Codex model picker, or `inherit`. Effort is `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, or `ultra`, where the model supports it. Never set a model the user hasn't confirmed they can use.

Panel roles take 2 to 6 seats (`candidate-graft-judge` 1 to 6). Repeating a model across seats gives independent attempts, not model diversity. Say so.

## 3. Preview

Prepare the chosen overrides using the [helper's input format](references/nstack-config.md#administrative-commands). Include the complete set of overrides the user wants for this client.

Run `python3 "<helper>" configure --input <overrides.json> --dry-run` and show each changed role's `before` and `after`. Fix validation errors with the user and preview again.

## 4. Apply

After the user confirms, run `python3 "<helper>" configure --input <overrides.json> --apply --plan-id <plan_id>`. On `stale_plan` (exit 5), preview again and get fresh confirmation. Delete the temp file.

## 5. Check dispatch

A configured model is not proof the client runs it. Probe at least one seat per distinct model with `spawn_agent` with `agent_type` `nstack-agent` and a `message` that starts with `[nstack role=<role> seat=<n>]`, followed by the brief and this brief:

```text
[nstack role=<role> seat=<n>] This is an nstack setup probe. Do not read, write, or run anything.
Reply with exactly one line: NSTACK-PROBE <role> <seat>
```

Record the result with `python3 "<helper>" record-verification --role <role> --seat <n> --status <verified|failed> --evidence "<observation>"`. Record `failed` when the launch is blocked or the model is rejected, and show the error. Record `verified` only when the client shows which model served the launch (the subagent's thread details), and quote it. A subagent's claim about its own model is not evidence. Otherwise leave the seat unverified.

## 6. Report

The overrides applied (or defaults in use), the effective model and effort per role from `status`, each probed seat as verified, failed, or unverified with the reason, and anything still blocked, including an untrusted hook. Re-running is safe; unchanged choices write nothing.

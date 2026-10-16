"""Behavior of nstack's model management helper and spawn hook.

Each test installs a copy of the helper into an isolated fake plugin tree and
runs it as a subprocess with HOME redirected to a temp dir, so no real user
configuration is read or written.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_HOOKS = ROOT / "src" / "plugins" / "nstack" / "hooks"
HOOK_DIR = {"claude": "hooks", "copilot": "com.github.copilot/hooks", "codex": "hooks"}
VERSION = "0.0.1"

ROLES = [
    "how-explorer",
    "how-explainer",
    "why-investigator",
    "why-synthesizer",
    "swarm-worker",
    "candidate-graft-runner",
    "candidate-graft-judge",
    "architect-runner",
    "review-panel-reviewer",
    "implementer",
    "implementer-hard",
    "judgment",
]
READ_ONLY = {"how-explorer", "how-explainer", "candidate-graft-judge", "review-panel-reviewer"}
AGENT_NAME = {
    "claude": "nstack:implementation:nstack-agent",
    "copilot": "nstack:nstack-agent",
    "codex": "nstack-agent",
}


def install(base: Path, client: str) -> Path:
    """Create a fake installed nstack plugin for one client; return the helper path."""
    root = base / "plugins with spaces" / client / "nstack"
    hooks = root / HOOK_DIR[client]
    hooks.mkdir(parents=True)
    shutil.copy2(SRC_HOOKS / "nstack_config.py", hooks / "nstack_config.py")
    manifest = json.dumps({"name": "nstack", "version": VERSION})
    if client == "claude":
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".claude-plugin" / "plugin.json").write_text(manifest)
    elif client == "copilot":
        (root / "plugin.json").write_text(manifest)
    else:
        (root / ".codex-plugin").mkdir(parents=True)
        (root / ".codex-plugin" / "plugin.json").write_text(manifest)
    return hooks / "nstack_config.py"


def plugin_root(helper: Path) -> Path:
    return next(parent for parent in helper.parents if parent.name == "nstack")


@pytest.fixture
def env(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    values = {k: v for k, v in os.environ.items() if k != "NSTACK_HOME"}
    values["HOME"] = str(home)
    return {"home": home, "vars": values, "tmp": tmp_path}


def run(helper: Path, env, *args, expect: int | None = 0, stdin: str | None = None) -> tuple[int, dict | None]:
    proc = subprocess.run(
        [sys.executable, str(helper), *args],
        capture_output=True,
        text=True,
        env=env["vars"],
        cwd=env["tmp"],
        input=stdin,
    )
    if expect is not None:
        assert proc.returncode == expect, proc.stdout + proc.stderr
    return proc.returncode, (json.loads(proc.stdout) if proc.stdout.strip() else None)


def overrides(client: str, roles: dict) -> dict:
    return {"schema_version": 1, "clients": {client: {"roles": roles}}}


def write_input(env, data: dict) -> Path:
    path = env["tmp"] / "overrides.json"
    path.write_text(json.dumps(data))
    return path


def configure(helper, env, data) -> tuple[dict, dict]:
    path = write_input(env, data)
    _, preview = run(helper, env, "configure", "--input", str(path), "--dry-run")
    _, applied = run(helper, env, "configure", "--input", str(path), "--apply", "--plan-id", preview["plan_id"])
    return preview, applied


def snapshot(home: Path) -> dict[str, bytes]:
    return {str(p.relative_to(home)): p.read_bytes() for p in sorted(home.rglob("*")) if p.is_file()}


def payload(client: str, args: dict) -> str:
    if client == "copilot":
        return json.dumps({"sessionId": "s", "timestamp": 1, "cwd": "/w", "toolName": "task", "toolArgs": args})
    tool = "Agent" if client == "claude" else "spawn_agent"
    return json.dumps({"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": args})


def launch(client: str, marker: str, agent: str | None = None, brief: str = "Do the task.") -> dict:
    if client == "codex":
        args = {"message": f"{marker} {brief}"}
        if agent is not False:
            args["agent_type"] = agent or AGENT_NAME["codex"]
        return args
    key = "subagent_type" if client == "claude" else "agent_type"
    return {key: agent or AGENT_NAME[client], "description": f"{marker} probe", "prompt": brief}


def hook(helper, env, client, args) -> dict | None:
    _, out = run(helper, env, "hook", stdin=payload(client, args))
    return out


def allowed_args(client: str, out: dict) -> dict:
    if client == "copilot":
        assert out["permissionDecision"] == "allow"
        return out["modifiedArgs"]
    inner = out["hookSpecificOutput"]
    assert inner["hookEventName"] == "PreToolUse"
    assert inner["permissionDecision"] == "allow"
    return inner["updatedInput"]


def denial(client: str, out: dict) -> str:
    if client == "copilot":
        assert out["permissionDecision"] == "deny"
        return out["permissionDecisionReason"]
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    return out["hookSpecificOutput"]["permissionDecisionReason"]


# --- catalog, defaults, status ---------------------------------------------------


@pytest.mark.parametrize("client", ["claude", "copilot", "codex"])
def test_roles_lists_catalog_and_defaults(env, client):
    helper = install(env["tmp"], client)
    _, data = run(helper, env, "roles")
    assert data["client"] == client
    assert [r["id"] for r in data["roles"]] == ROLES
    for role in data["roles"]:
        assert role["agent"] == ("nstack-reader" if role["id"] in READ_ONLY else "nstack-agent")
        assert role["min_seats"] <= len(role["default"]) <= role["max_seats"]
    assert (data["efforts"] == []) is (client == "claude")


def test_status_without_config_shows_defaults_and_writes_nothing(env):
    helper = install(env["tmp"], "copilot")
    before = snapshot(env["home"])
    _, data = run(helper, env, "status")
    assert snapshot(env["home"]) == before
    reviewer = data["roles"]["review-panel-reviewer"]
    assert reviewer["source"] == "default"
    assert reviewer["agent"] == "nstack-reader"
    assert [(s["model"], s["effort"]) for s in reviewer["seats"]] == [
        ("claude-opus-5.5", "high"),
        ("gpt-6.1-sol", "high"),
    ]
    assert all(s["runtime_verification"] == "unverified" for s in reviewer["seats"])


# --- configure ------------------------------------------------------------------


def test_dry_run_previews_without_writing(env):
    helper = install(env["tmp"], "codex")
    before = snapshot(env["home"])
    path = write_input(env, overrides("codex", {"implementer": {"model": "gpt-5.6-sol", "effort": "low"}}))
    _, data = run(helper, env, "configure", "--input", str(path), "--dry-run")
    assert data["applied"] is False
    assert [c["role"] for c in data["changes"]] == ["implementer"]
    assert data["changes"][0]["after"] == [{"model": "gpt-5.6-sol", "effort": "low"}]
    assert data["changes"][0]["before_source"] == "default"
    assert snapshot(env["home"]) == before


def test_apply_writes_only_overrides_and_status_reflects_them(env):
    helper = install(env["tmp"], "copilot")
    configure(helper, env, overrides("copilot", {"implementer": {"model": "gpt-5.4", "effort": "xhigh"}}))
    saved = json.loads((env["home"] / ".nstack" / "models.json").read_text())
    assert saved["clients"] == {"copilot": {"roles": {"implementer": [{"model": "gpt-5.4", "effort": "xhigh"}]}}}
    _, status = run(helper, env, "status")
    assert status["roles"]["implementer"]["source"] == "override"
    assert status["roles"]["judgment"]["source"] == "default"
    assert not (env["home"] / ".copilot").exists()


def test_apply_requires_matching_plan_id(env):
    helper = install(env["tmp"], "claude")
    path = write_input(env, overrides("claude", {"implementer": {"model": "haiku"}}))
    _, data = run(helper, env, "configure", "--input", str(path), "--apply", "--plan-id", "0000", expect=5)
    assert data["errors"][0]["code"] == "stale_plan"
    assert not (env["home"] / ".nstack").exists()


def test_apply_rejects_approval_when_choices_change_after_preview(env):
    helper = install(env["tmp"], "claude")
    path = write_input(env, overrides("claude", {"implementer": {"model": "haiku"}}))
    _, preview = run(helper, env, "configure", "--input", str(path), "--dry-run")
    write_input(env, overrides("claude", {"implementer": {"model": "opus"}}))
    _, data = run(helper, env, "configure", "--input", str(path), "--apply", "--plan-id", preview["plan_id"], expect=5)
    assert data["errors"][0]["code"] == "stale_plan"


def test_reapplying_same_choices_is_idempotent(env):
    helper = install(env["tmp"], "claude")
    configure(helper, env, overrides("claude", {"implementer": {"model": "haiku"}}))
    before = snapshot(env["home"])
    preview, _ = configure(helper, env, overrides("claude", {"implementer": {"model": "haiku"}}))
    assert preview["changes"] == [] and preview["config_changes"] is False
    assert snapshot(env["home"]) == before


def test_empty_roles_return_to_defaults(env):
    helper = install(env["tmp"], "claude")
    configure(helper, env, overrides("claude", {"implementer": {"model": "haiku"}}))
    preview, _ = configure(helper, env, overrides("claude", {}))
    assert preview["changes"][0]["after_source"] == "default"
    saved = json.loads((env["home"] / ".nstack" / "models.json").read_text())
    assert "claude" not in saved["clients"]


def test_configure_rejects_other_clients(env):
    helper = install(env["tmp"], "claude")
    path = write_input(env, overrides("codex", {"implementer": {"model": "gpt-5.6-sol"}}))
    _, data = run(helper, env, "configure", "--input", str(path), "--dry-run", expect=1)
    assert data["errors"][0]["code"] == "invalid_input"


def test_other_clients_entries_are_preserved(env):
    helper = install(env["tmp"], "copilot")
    nstack = env["home"] / ".nstack"
    nstack.mkdir()
    foreign = {"roles": {"implementer": [{"model": "x"}], "future-role": [{"model": "y"}]}}
    (nstack / "models.json").write_text(json.dumps({"schema_version": 1, "clients": {"codex": foreign}, "verification": {}}))
    configure(helper, env, overrides("copilot", {"implementer": {"model": "gpt-5.4"}}))
    saved = json.loads((nstack / "models.json").read_text())
    assert saved["clients"]["codex"] == foreign


@pytest.mark.parametrize(
    ("client", "roles", "fragment"),
    [
        ("claude", {"implementer": {"model": "claude-opus-5-5"}}, "only accepts sonnet, opus, haiku, fable"),
        ("claude", {"implementer": {"model": "opus", "effort": "high"}}, "no per-launch reasoning effort"),
        ("copilot", {"implementer": {"model": "<user-selected-model>"}}, "not a valid model id"),
        ("copilot", {"implementer": {"model": "gpt-5.4", "effort": "ultra"}}, "effort 'ultra'"),
        ("copilot", {"implementer": {"model": ""}}, "'model' is required"),
        ("copilot", {"implementer": [{"model": "a"}, {"model": "b"}]}, "single seat"),
        ("copilot", {"review-panel-reviewer": [{"model": "a"}]}, "needs 2 to 6 seats"),
        ("copilot", {"candidate-graft-judge": [{"model": "a"}] * 7}, "needs 1 to 6 seats"),
        ("copilot", {"implementer": {"model": "a", "temperature": 1}}, "unknown keys"),
        ("copilot", {"review-panel-lead": {"model": "a"}}, "unknown roles"),
        ("codex", {"implementer": {"model": "gpt-5.6-sol", "effort": "extreme"}}, "effort 'extreme'"),
    ],
)
def test_invalid_overrides_are_rejected(env, client, roles, fragment):
    helper = install(env["tmp"], client)
    path = write_input(env, overrides(client, roles))
    _, data = run(helper, env, "configure", "--input", str(path), "--dry-run", expect=1)
    assert data["errors"][0]["code"] == "invalid_config"
    assert fragment in data["errors"][0]["message"]


def test_malformed_input_json_is_reported(env):
    helper = install(env["tmp"], "claude")
    path = env["tmp"] / "bad.json"
    path.write_text("{not json")
    _, data = run(helper, env, "configure", "--input", str(path), "--dry-run", expect=1)
    assert data["errors"][0]["code"] == "invalid_input"


def test_invalid_saved_entry_is_reported_and_replaceable(env):
    helper = install(env["tmp"], "copilot")
    nstack = env["home"] / ".nstack"
    nstack.mkdir()
    bad = {"schema_version": 1, "clients": {"copilot": {"roles": {"implementer": {"model": 42}}}}, "verification": {}}
    (nstack / "models.json").write_text(json.dumps(bad))
    _, status = run(helper, env, "status", expect=1)
    assert status["errors"][0]["code"] == "invalid_config"
    configure(helper, env, overrides("copilot", {"implementer": {"model": "gpt-5.4"}}))
    _, status = run(helper, env, "status")
    assert status["roles"]["implementer"]["seats"][0]["model"] == "gpt-5.4"


# --- verification -------------------------------------------------------------


def test_verification_is_recorded_and_invalidated_by_a_model_change(env):
    helper = install(env["tmp"], "copilot")
    run(
        helper, env, "record-verification", "--role", "implementer", "--status", "verified",
        "--evidence", "subagent.configured showed claude-sonnet-5 medium",
    )
    _, status = run(helper, env, "status")
    assert status["roles"]["implementer"]["seats"][0]["runtime_verification"] == "verified"
    configure(helper, env, overrides("copilot", {"implementer": {"model": "gpt-5.4"}}))
    _, status = run(helper, env, "status")
    assert status["roles"]["implementer"]["seats"][0]["runtime_verification"] == "unverified"


def test_verification_requires_evidence_and_an_existing_seat(env):
    helper = install(env["tmp"], "claude")
    _, data = run(
        helper, env, "record-verification", "--role", "implementer", "--status", "verified", "--evidence", " ", expect=1
    )
    assert data["errors"][0]["code"] == "invalid_input"
    _, data = run(
        helper, env, "record-verification", "--role", "review-panel-reviewer", "--seat", "3",
        "--status", "verified", "--evidence", "x", expect=1,
    )
    assert data["errors"][0]["code"] == "unknown_seat"


# --- hook -----------------------------------------------------------------------


@pytest.mark.parametrize("client", ["claude", "copilot", "codex"])
def test_hook_ignores_launches_without_a_marker(env, client):
    helper = install(env["tmp"], client)
    if client == "codex":
        args = {"agent_type": "worker", "message": "unrelated"}
    else:
        key = "subagent_type" if client == "claude" else "agent_type"
        args = {key: "explore", "description": "unrelated", "prompt": "unrelated"}
    assert hook(helper, env, client, args) is None


@pytest.mark.parametrize(
    "stdin",
    [
        "",
        "garbage",
        "[]",
        json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}),
        json.dumps({"toolName": "bash", "toolArgs": {"command": "grep -r '[nstack role=implementer]' ."}}),
        json.dumps({"toolName": "task", "toolArgs": None}),
    ],
)
def test_hook_passes_through_unparseable_or_unrelated_input(env, stdin):
    helper = install(env["tmp"], "copilot")
    code, out = run(helper, env, "hook", stdin=stdin)
    assert code == 0 and out is None


@pytest.mark.parametrize("client", ["claude", "copilot", "codex"])
def test_hook_blocks_nstack_agents_launched_without_a_marker(env, client):
    helper = install(env["tmp"], client)
    args = launch(client, "")
    reason = denial(client, hook(helper, env, client, args))
    assert "nstack marker" in reason


def test_hook_applies_claude_defaults_without_effort(env):
    helper = install(env["tmp"], "claude")
    args = allowed_args("claude", hook(helper, env, "claude", launch("claude", "[nstack role=review-panel-reviewer seat=2]")))
    assert args["model"] == "sonnet"
    assert args["subagent_type"] == "nstack:implementation:nstack-reader"
    assert "reasoning_effort" not in args
    assert "[nstack-hook] role=review-panel-reviewer seat=2 agent=nstack-reader model=sonnet effort=default source=default" in args["prompt"]
    assert args["description"].startswith("[nstack role=review-panel-reviewer seat=2]")


def test_hook_applies_copilot_model_and_effort_per_seat(env):
    helper = install(env["tmp"], "copilot")
    seats = {}
    for seat in (1, 2):
        out = hook(helper, env, "copilot", launch("copilot", f"[nstack role=review-panel-reviewer seat={seat}]"))
        args = allowed_args("copilot", out)
        seats[seat] = (args["model"], args["reasoning_effort"], args["agent_type"])
    assert seats == {
        1: ("claude-opus-5.5", "high", "nstack:nstack-reader"),
        2: ("gpt-6.1-sol", "high", "nstack:nstack-reader"),
    }


def test_hook_applies_codex_overrides_and_sets_a_missing_agent_type(env):
    helper = install(env["tmp"], "codex")
    configure(helper, env, overrides("codex", {"implementer-hard": {"model": "gpt-5.6-terra", "effort": "xhigh"}}))
    args = allowed_args("codex", hook(helper, env, "codex", launch("codex", "[nstack role=implementer-hard]", agent=False)))
    assert args["agent_type"] == "nstack-agent"
    assert args["model"] == "gpt-5.6-terra"
    assert args["reasoning_effort"] == "xhigh"
    assert "source=override" in args["message"]


def test_hook_replaces_models_the_parent_chose(env):
    helper = install(env["tmp"], "copilot")
    args = launch("copilot", "[nstack role=implementer]")
    args.update({"model": "gpt-5-mini", "reasoning_effort": "low"})
    new = allowed_args("copilot", hook(helper, env, "copilot", args))
    assert (new["model"], new["reasoning_effort"]) == ("claude-sonnet-5", "medium")


def test_hook_inherit_removes_the_model(env):
    helper = install(env["tmp"], "copilot")
    configure(helper, env, overrides("copilot", {"implementer": {"model": "inherit"}}))
    args = launch("copilot", "[nstack role=implementer]")
    args["model"] = "gpt-5-mini"
    new = allowed_args("copilot", hook(helper, env, "copilot", args))
    assert "model" not in new and "reasoning_effort" not in new


def test_hook_routes_writer_roles_to_nstack_agent(env):
    helper = install(env["tmp"], "claude")
    args = launch("claude", "[nstack role=why-investigator]", agent="nstack:implementation:nstack-reader")
    new = allowed_args("claude", hook(helper, env, "claude", args))
    assert new["subagent_type"] == "nstack:implementation:nstack-agent"


def test_hook_footer_names_files_to_read_first(env):
    helper = install(env["tmp"], "copilot")
    root = plugin_root(helper)
    tier = allowed_args("copilot", hook(helper, env, "copilot", launch("copilot", "[nstack role=judgment]")))
    assert f"Read first: {root / 'skills' / 'nstack-flow' / 'SKILL.md'}" in tier["prompt"]
    assert tier["prompt"].count("Read first:") == 1
    specialist = allowed_args("copilot", hook(helper, env, "copilot", launch("copilot", "[nstack role=how-explorer]")))
    assert "[nstack-hook] role=how-explorer" in specialist["prompt"]
    assert "Read first" not in specialist["prompt"]


def test_hook_replaces_an_existing_footer_instead_of_stacking(env):
    helper = install(env["tmp"], "copilot")
    first = allowed_args("copilot", hook(helper, env, "copilot", launch("copilot", "[nstack role=implementer]")))
    again = allowed_args("copilot", hook(helper, env, "copilot", first))
    assert again["prompt"].count("[nstack-hook] role=") == 1


@pytest.mark.parametrize(
    ("marker", "agent", "fragment"),
    [
        ("[nstack role=review-panel-lead]", None, "Unknown nstack role"),
        ("[nstack role=review-panel-reviewer seat=3]", None, "seat 3 does not exist"),
        ("[nstack role=implementer]", "general-purpose", "must run on the nstack-agent agent"),
        ("[nstack role=implementer seat=x]", None, "seat must be a number"),
        ("[nstack role=review-panel-reviewer seat=0]", None, "seat 0 does not exist"),
    ],
)
def test_hook_denies_invalid_nstack_launches(env, marker, agent, fragment):
    helper = install(env["tmp"], "copilot")
    reason = denial("copilot", hook(helper, env, "copilot", launch("copilot", marker, agent=agent)))
    assert fragment in reason


def test_hook_denies_when_the_saved_configuration_is_invalid(env):
    helper = install(env["tmp"], "claude")
    nstack = env["home"] / ".nstack"
    nstack.mkdir()
    (nstack / "models.json").write_text("{broken")
    reason = denial("claude", hook(helper, env, "claude", launch("claude", "[nstack role=implementer]")))
    assert "not valid JSON" in reason


def test_hook_never_writes(env):
    helper = install(env["tmp"], "codex")
    before = snapshot(env["home"])
    hook(helper, env, "codex", launch("codex", "[nstack role=swarm-worker]"))
    assert snapshot(env["home"]) == before


@pytest.mark.parametrize(
    ("client", "tool", "acts"),
    [
        ("claude", "mcp__x__runAgent", False),
        ("copilot", "subtask", False),
        ("codex", "multi_agent_v1spawn_agent", True),
    ],
)
def test_hook_acts_only_on_the_clients_spawn_tool(env, client, tool, acts):
    helper = install(env["tmp"], client)
    data = json.loads(payload(client, launch(client, "[nstack role=implementer]")))
    data["toolName" if client == "copilot" else "tool_name"] = tool
    _, out = run(helper, env, "hook", stdin=json.dumps(data))
    assert (out is not None) is acts


def test_marker_quoted_inside_a_brief_is_ignored(env):
    helper = install(env["tmp"], "copilot")
    quoted = "Review this diff:\n+ Mark launches like [nstack role=review-panel-reviewer seat=2]."
    args = {"agent_type": "code-review", "description": "review the change", "prompt": quoted}
    assert hook(helper, env, "copilot", args) is None


def test_description_marker_wins_over_markers_in_the_brief(env):
    helper = install(env["tmp"], "copilot")
    args = {
        "prompt": "[nstack role=swarm-worker] appears in this brief as an example",
        "agent_type": "nstack:nstack-agent",
        "description": "[nstack role=implementer-hard] hard change",
    }
    new = allowed_args("copilot", hook(helper, env, "copilot", args))
    assert (new["model"], new["reasoning_effort"]) == ("claude-opus-5.5", "high")
    assert "role=implementer-hard" in new["prompt"]


def test_marker_on_the_first_line_of_the_brief_is_accepted(env):
    helper = install(env["tmp"], "claude")
    args = {"subagent_type": "nstack:implementation:nstack-agent", "prompt": "[nstack role=judgment]\nWrite the PR text."}
    new = allowed_args("claude", hook(helper, env, "claude", args))
    assert new["model"] == "opus"


def test_codex_marker_must_start_the_message(env):
    helper = install(env["tmp"], "codex")
    args = {"agent_type": "worker", "message": "Summarize. Example marker: [nstack role=implementer]"}
    assert hook(helper, env, "codex", args) is None


def test_hook_steps_aside_on_old_python(env):
    helper = install(env["tmp"], "copilot")
    shim = (
        "import runpy, sys; sys.version_info = (3, 9, 0, 'final', 0); "
        f"sys.argv = [{str(helper)!r}] + sys.argv[1:]; runpy.run_path({str(helper)!r}, run_name='__main__')"
    )
    hooked = subprocess.run([sys.executable, "-c", shim, "hook"], input=payload("copilot", launch("copilot", "[nstack role=implementer]")),
                            capture_output=True, text=True, env=env["vars"])
    assert (hooked.returncode, hooked.stdout) == (0, "")
    started = subprocess.run([sys.executable, "-c", shim, "session-start"], input="{}", capture_output=True, text=True, env=env["vars"])
    assert (started.returncode, started.stdout) == (0, "")
    other = subprocess.run([sys.executable, "-c", shim, "status"], capture_output=True, text=True, env=env["vars"])
    assert other.returncode == 1 and "unsupported_python" in other.stdout


# --- session start ----------------------------------------------------------------


def session_context(helper, env, client) -> str:
    _, out = run(helper, env, "session-start", stdin="{}")
    if client == "copilot":
        return out["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    return out["hookSpecificOutput"]["additionalContext"]


def test_session_start_lists_default_panels_for_copilot(env):
    helper = install(env["tmp"], "copilot")
    context = session_context(helper, env, "copilot")
    assert context.startswith("nstack panels (reference for nstack skills; no action needed): ")
    assert "review-panel-reviewer 2 seats (1: claude-opus-5.5 high, 2: gpt-6.1-sol high)" in context
    assert "candidate-graft-judge 2 seats" in context
    assert "implementer" not in context.replace("candidate-graft", "")


@pytest.mark.parametrize("client", ["claude", "codex"])
def test_session_start_uses_the_clients_output_shape(env, client):
    helper = install(env["tmp"], client)
    context = session_context(helper, env, client)
    assert "architect-runner 2 seats" in context


def test_session_start_reflects_overrides(env):
    helper = install(env["tmp"], "codex")
    three = [{"model": "gpt-5.6-sol", "effort": "high"}] * 3
    configure(helper, env, overrides("codex", {"review-panel-reviewer": three}))
    context = session_context(helper, env, "codex")
    assert "review-panel-reviewer 3 seats (1: gpt-5.6-sol high, 2: gpt-5.6-sol high, 3: gpt-5.6-sol high)" in context


def test_session_start_reports_an_invalid_configuration(env):
    helper = install(env["tmp"], "claude")
    nstack = env["home"] / ".nstack"
    nstack.mkdir()
    (nstack / "models.json").write_text("{broken")
    assert "Run setup-nstack" in session_context(helper, env, "claude")


def test_session_start_never_writes(env):
    helper = install(env["tmp"], "copilot")
    before = snapshot(env["home"])
    session_context(helper, env, "copilot")
    assert snapshot(env["home"]) == before

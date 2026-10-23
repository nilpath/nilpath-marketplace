#!/usr/bin/env python3
"""nstack's model hook: role catalog, built-in defaults, user overrides, and hook entry points.

Every nstack subagent launch carries a marker such as
`[nstack role=review-panel-reviewer seat=2]`. The plugin's pre-tool hook (the
`hook` command) reads the marker, resolves the role's model and reasoning effort
(the user's override in ~/.nstack/models.json, else the built-in default for
this client), writes them into the launch call, routes read-only roles to
nstack-reader, and appends an `[nstack-hook]` block naming the files the
subagent reads first. Launches without a marker pass through untouched. At session start, the
`session-start` command adds one short context line listing each panel role's
seats and models, so panel skills know how many seats to launch.

This script ships next to the plugin's hooks.json.

Commands (all print JSON on stdout):
  roles                                       role catalog, defaults, supported efforts
  status                                      effective model per role and seat (read-only)
  configure --input F --dry-run               preview override changes (no writes)
  configure --input F --apply --plan-id ID    apply a previewed change
  record-verification --role R [--seat N] --status S --evidence E
  hook                                        pre-tool hook; reads the client's payload on stdin
  session-start                               session-start hook; prints the panel context

Standard library only; Python 3.11+.
"""

from __future__ import annotations

import sys

if sys.version_info < (3, 11):  # pragma: no cover - exercised only on old interpreters
    if sys.argv[1:2] in (["hook"], ["session-start"]):
        # Never block a client's launches. nstack agents report the missing [nstack-hook] footer instead.
        sys.exit(0)
    sys.stdout.write(
        '{"ok": false, "errors": [{"code": "unsupported_python", '
        '"message": "nstack_config.py requires Python 3.11 or newer.", '
        '"repair": "Install Python 3.11+ and run it as python3."}]}\n'
    )
    sys.exit(1)

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
SCRIPT_DIR = Path(__file__).resolve().parent
MANIFESTS = (
    ("claude", Path(".claude-plugin") / "plugin.json"),
    ("codex", Path(".codex-plugin") / "plugin.json"),
    ("copilot", Path("plugin.json")),
)


def find_plugin_root(start: Path = SCRIPT_DIR) -> Path:
    """The installed plugin root: the nearest ancestor holding a plugin manifest.
    Claude and Codex ship this script in hooks/, Copilot in com.github.copilot/hooks/."""
    for candidate in (start.parent, *start.parent.parents):
        if any((candidate / manifest).is_file() for _, manifest in MANIFESTS):
            return candidate
    return start.parent


PLUGIN_ROOT = find_plugin_root()

INHERIT = "inherit"
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$")
MARKER_RE = re.compile(r"\[nstack role=([a-z0-9-]+)(?:\s+seat=([^\]\s]+))?\]")
FOOTER_TAG = "[nstack-hook]"
WRITER_AGENT = "nstack-agent"
READER_AGENT = "nstack-reader"
NSTACK_AGENTS = (WRITER_AGENT, READER_AGENT)


@dataclass(frozen=True)
class Role:
    id: str
    description: str
    tier: str
    panel: bool
    min_seats: int
    max_seats: int
    read_only: bool

    @property
    def agent(self) -> str:
        return READER_AGENT if self.read_only else WRITER_AGENT


ROLES: dict[str, Role] = {
    role.id: role
    for role in (
        Role("how-explorer", "Traces one angle of a subsystem for the how skill.", "fast", False, 1, 1, True),
        Role("how-explainer", "Writes the how skill's architectural explanation.", "strong", False, 1, 1, True),
        Role("why-investigator", "Gathers evidence from one source category for the why skill.", "fast", False, 1, 1, False),
        Role("why-synthesizer", "Synthesizes why-investigator findings into a cited answer.", "strong", False, 1, 1, False),
        Role("swarm-worker", "Completes one slice or race arm of a swarm.", "fast", False, 1, 1, False),
        Role("candidate-graft-runner", "Produces one independent candidate for candidate-graft.", "panel", True, 2, 6, False),
        Role("candidate-graft-judge", "Cross-judges candidate-graft candidates; one pool seat is used per run.", "judge", True, 1, 6, True),
        Role("architect-runner", "Produces one candidate design package for architect.", "panel", True, 2, 6, False),
        Role("review-panel-reviewer", "Reviews a change independently for review-panel.", "panel", True, 2, 6, True),
        Role("implementer", "Routine implementation and helper briefs in playbook steps.", "fast", False, 1, 1, False),
        Role("implementer-hard", "The hardest changes: cross-cutting design, concurrency, subtle algorithms.", "strong", False, 1, 1, False),
        Role("judgment", "Judgment and prose briefs: analysis, second opinions, pull request text.", "strong", False, 1, 1, False),
    )
}

# Delegate tiers that read nstack-flow's rules before working. Specialist roles get their
# instructions from the calling skill's brief instead.
FLOW_ROLES = frozenset({"implementer", "implementer-hard", "judgment"})

CLIENTS = ("claude", "copilot", "codex")
CLIENT_NAMES = {"claude": "Claude Code", "copilot": "GitHub Copilot CLI", "codex": "Codex"}
CLAUDE_MODELS = ("sonnet", "opus", "haiku", "fable")
EFFORTS: dict[str, tuple[str, ...]] = {
    "claude": (),
    "copilot": ("low", "medium", "high", "xhigh", "max"),
    "codex": ("minimal", "low", "medium", "high", "xhigh", "max", "ultra"),
}
MODEL_NOTES = {
    "claude": "Claude Code accepts only the aliases sonnet, opus, haiku, and fable per launch, and no per-launch effort.",
    "copilot": "Use model ids as Copilot lists them (for example claude-opus-5.5). Allowed effort levels depend on the model.",
    "codex": "Use model ids your Codex account can select. Allowed effort levels depend on the model.",
}

# Built-in defaults per client and tier. Overrides in ~/.nstack/models.json replace these per role.
DEFAULT_TIERS: dict[str, dict[str, list[dict]]] = {
    "claude": {
        "fast": [{"model": "sonnet"}],
        "strong": [{"model": "opus"}],
        "panel": [{"model": "opus"}, {"model": "sonnet"}],
        "judge": [{"model": "opus"}, {"model": "sonnet"}],
    },
    "copilot": {
        "fast": [{"model": "claude-sonnet-5", "effort": "medium"}],
        "strong": [{"model": "claude-opus-5.5", "effort": "high"}],
        "panel": [{"model": "claude-opus-5.5", "effort": "high"}, {"model": "gpt-6.1-sol", "effort": "high"}],
        "judge": [{"model": "gpt-6.1-sol", "effort": "high"}, {"model": "claude-opus-5.5", "effort": "high"}],
    },
    "codex": {
        "fast": [{"model": "gpt-5.6-luna", "effort": "medium"}],
        "strong": [{"model": "gpt-5.6-sol", "effort": "high"}],
        "panel": [{"model": "gpt-5.6-sol", "effort": "high"}, {"model": "gpt-5.6-terra", "effort": "high"}],
        "judge": [{"model": "gpt-5.6-sol", "effort": "high"}],
    },
}

# Spawn tools per client. The hook acts only on these, even if a client ignores the configured matcher.
SPAWN_TOOLS = {"claude": ("Agent", "Task"), "copilot": ("task",), "codex": ("spawn_agent", "Agent")}



def is_spawn_tool(client: str, tool) -> bool:
    if not isinstance(tool, str):
        return False
    if tool in SPAWN_TOOLS[client]:
        return True
    # Codex can report its collaboration tools with a namespace prefix.
    return client == "codex" and tool.endswith("spawn_agent")


# Launch-call field names per client.
AGENT_KEY = {"claude": "subagent_type", "copilot": "agent_type", "codex": "agent_type"}
PROMPT_KEY = {"claude": "prompt", "copilot": "prompt", "codex": "message"}
EFFORT_KEY = {"copilot": "reasoning_effort", "codex": "reasoning_effort"}
SETUP_REPAIR = "Run the setup-nstack skill to review or fix nstack's model configuration."


class NstackError(Exception):
    def __init__(self, code: str, message: str, repair: str = "", exit_code: int = 1, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.repair = repair
        self.exit_code = exit_code
        self.extra = extra

    def as_dict(self) -> dict:
        data = {"code": self.code, "message": self.message, "repair": self.repair}
        data.update(self.extra)
        return data


# --- small utilities ------------------------------------------------------------


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(data) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def detect_distribution(root: Path = PLUGIN_ROOT) -> tuple[str, str]:
    """Return (client, version) for the installed nstack tree this script belongs to."""
    for client, rel in MANIFESTS:
        manifest = root / rel
        if manifest.is_file():
            try:
                version = str(json.loads(manifest.read_text(encoding="utf-8")).get("version", "unknown"))
            except (OSError, json.JSONDecodeError):
                version = "unknown"
            return client, version
    raise NstackError(
        "unknown_distribution",
        f"Cannot find an nstack plugin manifest under {root}.",
        "Run the helper from an installed nstack plugin (Claude, Copilot, or Codex distribution).",
    )


def config_path() -> Path:
    override = os.environ.get("NSTACK_HOME")
    return (Path(override) if override else Path.home() / ".nstack") / "models.json"


# --- validation -----------------------------------------------------------------


def _invalid(message: str) -> NstackError:
    return NstackError("invalid_config", message, "Correct the role choices and preview again.")


def normalize_seats(client: str, role_id: str, value) -> list[dict]:
    role = ROLES[role_id]
    where = f"{client}.{role_id}"
    items = value if isinstance(value, list) else [value]
    seats: list[dict] = []
    for index, item in enumerate(items, start=1):
        label = f"{where}[{index}]" if role.panel else where
        if isinstance(item, str):
            item = {"model": item}
        if not isinstance(item, dict):
            raise _invalid(f"{label}: expected an object with 'model' (and optional 'effort').")
        unknown = sorted(set(item) - {"model", "effort"})
        if unknown:
            raise _invalid(f"{label}: unknown keys {unknown}.")
        model = item.get("model")
        if not isinstance(model, str) or not model:
            raise _invalid(f"{label}: 'model' is required and must be a non-empty string.")
        if model != INHERIT:
            if client == "claude" and model not in CLAUDE_MODELS:
                raise _invalid(
                    f"{label}: Claude Code only accepts {', '.join(CLAUDE_MODELS)}, or 'inherit', per launch; got '{model}'."
                )
            if not MODEL_RE.match(model):
                raise _invalid(f"{label}: '{model}' is not a valid model id. Use the client's exact id, or 'inherit'.")
        seat = {"model": model}
        effort = item.get("effort")
        if effort is not None:
            supported = EFFORTS[client]
            if not supported:
                raise _invalid(f"{label}: {CLIENT_NAMES[client]} has no per-launch reasoning effort; remove 'effort'.")
            if effort not in supported:
                raise _invalid(f"{label}: effort '{effort}' is not one of {list(supported)} for {CLIENT_NAMES[client]}.")
            seat["effort"] = effort
        seats.append(seat)
    if isinstance(value, list) and not role.panel and len(seats) != 1:
        raise _invalid(f"{where}: this role takes a single seat.")
    if not role.min_seats <= len(seats) <= role.max_seats:
        bounds = f"{role.min_seats} to {role.max_seats} seats" if role.panel else "exactly one seat"
        raise _invalid(f"{where}: needs {bounds}, got {len(seats)}.")
    return seats


def normalize_overrides(client: str, data) -> dict[str, list[dict]]:
    if not isinstance(data, dict) or set(data) != {"roles"} or not isinstance(data["roles"], dict):
        raise _invalid(f"{client}: expected exactly {{\"roles\": {{...}}}}.")
    unknown = sorted(set(data["roles"]) - set(ROLES))
    if unknown:
        raise _invalid(f"{client}: unknown roles {unknown}. Known roles: {list(ROLES)}.")
    return {role_id: normalize_seats(client, role_id, value) for role_id, value in data["roles"].items()}


def default_seats(client: str, role_id: str) -> list[dict]:
    return copy.deepcopy(DEFAULT_TIERS[client][ROLES[role_id].tier])


# --- state ----------------------------------------------------------------------


def load_state() -> dict:
    """Load models.json. Every client's saved entry is kept verbatim so writes never drop
    another install's data; only this script's view of its own client is validated."""
    path = config_path()
    state = {"schema_version": SCHEMA_VERSION, "clients": {}, "verification": {}}
    text = read_text(path)
    if text is None:
        return state
    repair = f"Fix {path} by hand, or move it aside to return to nstack's built-in defaults."
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NstackError("invalid_config", f"{path} is not valid JSON: {exc}.", repair) from exc
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise NstackError("invalid_config", f"{path} has an unsupported schema_version.", repair)
    for key in ("clients", "verification"):
        value = data.get(key, {})
        if not isinstance(value, dict):
            raise NstackError("invalid_config", f"{path}: '{key}' must be an object.", repair)
        state[key] = value
    return state


def client_overrides(state: dict, client: str) -> dict[str, list[dict]]:
    """Validated overrides for one client. Unknown roles (from another nstack version) are ignored."""
    entry = state["clients"].get(client)
    if entry is None:
        return {}
    if not isinstance(entry, dict) or not isinstance(entry.get("roles"), dict):
        raise NstackError(
            "invalid_config",
            f"The saved nstack configuration for {CLIENT_NAMES[client]} is not a {{\"roles\": {{...}}}} object.",
            SETUP_REPAIR,
        )
    known = {role_id: value for role_id, value in entry["roles"].items() if role_id in ROLES}
    try:
        return {role_id: normalize_seats(client, role_id, value) for role_id, value in known.items()}
    except NstackError as exc:
        raise NstackError(
            "invalid_config", f"The saved nstack configuration is invalid: {exc.message}", SETUP_REPAIR
        ) from exc


def effective_seats(client: str, overrides: dict[str, list[dict]], role_id: str) -> tuple[list[dict], str]:
    if role_id in overrides:
        return overrides[role_id], "override"
    return default_seats(client, role_id), "default"


def serialize_state(state: dict) -> str:
    return json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def verification_key(client: str, role_id: str, seat_no: int) -> str:
    return f"{client}/{role_id}/{seat_no}"


def seat_fingerprint(client: str, role_id: str, seat_no: int, seat: dict) -> str:
    return sha256_text(canonical_json({"client": client, "role": role_id, "seat": seat_no, "config": seat}))


def verification_status(state: dict, client: str, role_id: str, seat_no: int, seat: dict) -> str:
    record = state["verification"].get(verification_key(client, role_id, seat_no))
    if isinstance(record, dict) and record.get("fingerprint") == seat_fingerprint(client, role_id, seat_no, seat):
        return str(record.get("status", "unverified"))
    return "unverified"


def describe_role(state: dict, client: str, overrides: dict, role_id: str) -> dict:
    role = ROLES[role_id]
    seats, source = effective_seats(client, overrides, role_id)
    return {
        "panel": role.panel,
        "read_only": role.read_only,
        "agent": role.agent,
        "source": source,
        "seats": [
            {
                "seat": seat_no,
                "model": seat["model"],
                "effort": seat.get("effort"),
                "runtime_verification": verification_status(state, client, role_id, seat_no, seat),
            }
            for seat_no, seat in enumerate(seats, start=1)
        ],
    }


# --- commands -------------------------------------------------------------------


def cmd_roles(_args) -> dict:
    client, version = detect_distribution()
    return {
        "ok": True,
        "nstack_version": version,
        "client": client,
        "client_name": CLIENT_NAMES[client],
        "efforts": list(EFFORTS[client]),
        "model_note": MODEL_NOTES[client],
        "config_path": str(config_path()),
        "roles": [
            {
                "id": role.id,
                "description": role.description,
                "agent": role.agent,
                "read_only": role.read_only,
                "panel": role.panel,
                "min_seats": role.min_seats,
                "max_seats": role.max_seats,
                "default": default_seats(client, role.id),
            }
            for role in ROLES.values()
        ],
    }


def cmd_status(_args) -> dict:
    client, version = detect_distribution()
    state = load_state()
    result = {
        "ok": True,
        "nstack_version": version,
        "client": client,
        "client_name": CLIENT_NAMES[client],
        "config_path": str(config_path()),
    }
    try:
        overrides = client_overrides(state, client)
    except NstackError as exc:
        result.update({"ok": False, "errors": [exc.as_dict()]})
        return result
    result["roles"] = {role_id: describe_role(state, client, overrides, role_id) for role_id in ROLES}
    return result


def parse_choices(path: Path, client: str) -> dict[str, list[dict]]:
    text = read_text(path)
    if text is None:
        raise NstackError("invalid_input", f"Input file not found: {path}.", "Write the role choices to a JSON file first.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NstackError("invalid_input", f"{path} is not valid JSON: {exc}.", "Fix the JSON and preview again.") from exc
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise NstackError("invalid_input", f"Input must be an object with \"schema_version\": {SCHEMA_VERSION}.")
    extra = sorted(set(data) - {"schema_version", "clients"})
    if extra:
        raise NstackError("invalid_input", f"Unknown top-level keys {extra}.")
    clients = data.get("clients")
    if not isinstance(clients, dict) or set(clients) != {client}:
        raise NstackError(
            "invalid_input",
            f"Input must configure exactly this client under \"clients\": {client}.",
            f"This is the {CLIENT_NAMES[client]} installation of nstack; other clients are configured from their own installation.",
        )
    return normalize_overrides(client, clients[client])


def cmd_configure(args) -> dict:
    client, _version = detect_distribution()
    new_overrides = parse_choices(Path(args.input), client)
    state = load_state()
    try:
        old_overrides = client_overrides(state, client)
    except NstackError:
        old_overrides = {}  # an invalid saved entry is exactly what configure replaces

    new_state = copy.deepcopy(state)
    if new_overrides:
        new_state["clients"][client] = {"roles": new_overrides}
    else:
        new_state["clients"].pop(client, None)
    config_text = serialize_state(new_state)
    current_text = read_text(config_path())

    changes = []
    for role_id in ROLES:
        before, before_source = effective_seats(client, old_overrides, role_id)
        after, after_source = effective_seats(client, new_overrides, role_id)
        if before != after or before_source != after_source:
            changes.append(
                {"role": role_id, "before": before, "before_source": before_source, "after": after, "after_source": after_source}
            )
    plan_id = sha256_text(
        canonical_json({"old": sha256_text(current_text) if current_text is not None else None, "new": sha256_text(config_text)})
    )[:16]
    result = {
        "ok": True,
        "client": client,
        "config_path": str(config_path()),
        "plan_id": plan_id,
        "config_changes": current_text != config_text,
        "changes": changes,
    }
    if args.dry_run:
        return {**result, "mode": "dry-run", "applied": False}
    if args.plan_id != plan_id:
        raise NstackError(
            "stale_plan",
            "The configuration changed since the preview, or the plan id does not match.",
            "Run configure --dry-run again, show the new preview to the user, and apply with its plan id.",
            exit_code=5,
            plan_id=plan_id,
        )
    if current_text != config_text:
        atomic_write(config_path(), config_text)
    return {**result, "mode": "apply", "applied": True}


def cmd_record_verification(args) -> dict:
    client, _version = detect_distribution()
    if args.role not in ROLES:
        raise NstackError("unknown_role", f"Unknown role '{args.role}'.", "Use a role id from the roles command.")
    if not args.evidence.strip():
        raise NstackError("invalid_input", "Verification evidence must not be empty.", "Describe what the client showed.")
    state = load_state()
    seats, _source = effective_seats(client, client_overrides(state, client), args.role)
    if not 1 <= args.seat <= len(seats):
        raise NstackError("unknown_seat", f"{args.role} has {len(seats)} seat(s); seat {args.seat} does not exist.")
    seat = seats[args.seat - 1]
    state["verification"][verification_key(client, args.role, args.seat)] = {
        "status": args.status,
        "evidence": args.evidence.strip(),
        "fingerprint": seat_fingerprint(client, args.role, args.seat, seat),
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    atomic_write(config_path(), serialize_state(state))
    return {"ok": True, "client": client, "role": args.role, "seat": args.seat, "runtime_verification": args.status}


# --- the spawn hook -------------------------------------------------------------


def _first_line(value) -> str:
    return value.lstrip().splitlines()[0] if isinstance(value, str) and value.strip() else ""


def find_marker(client: str, args: dict):
    """Find the marker only where skills put it: the start of the description, else the first
    line of the brief. A marker quoted elsewhere in a brief (a diff, a doc) is ignored."""
    if client == "codex":
        places = [_first_line(args.get("message"))]
    else:
        places = [_first_line(args.get("description")), _first_line(args.get(PROMPT_KEY[client]))]
    for text in places:
        match = MARKER_RE.match(text)
        if match:
            return match
    return None


def read_first(role_id: str) -> list[Path]:
    if role_id in FLOW_ROLES:
        return [
            PLUGIN_ROOT / "skills" / "nstack-flow" / "SKILL.md",
        ]
    return []


class HookDenied(Exception):
    pass


def rewrite_launch(client: str, args: dict, role_id: str, seat_no: int) -> dict:
    """Return the rewritten launch arguments for one nstack role seat, or raise HookDenied."""
    if role_id not in ROLES:
        raise HookDenied(f"Unknown nstack role '{role_id}'. Known roles: {', '.join(ROLES)}.")
    role = ROLES[role_id]
    try:
        overrides = client_overrides(load_state(), client)
    except NstackError as exc:
        raise HookDenied(f"{exc.message} {exc.repair}") from exc
    seats, source = effective_seats(client, overrides, role_id)
    if not 1 <= seat_no <= len(seats):
        raise HookDenied(f"nstack role {role_id} has {len(seats)} seat(s); seat {seat_no} does not exist.")
    seat = seats[seat_no - 1]

    new_args = dict(args)
    agent_key = AGENT_KEY[client]
    current = new_args.get(agent_key)
    if isinstance(current, str) and current:
        prefix, sep, name = current.rpartition(":")
        if name not in NSTACK_AGENTS:
            raise HookDenied(
                f"nstack role {role_id} must run on the {role.agent} agent, not '{current}'. "
                f"Launch {role.agent} with the same marker."
            )
        new_args[agent_key] = f"{prefix}{sep}{role.agent}"
    elif client == "codex":
        new_args[agent_key] = role.agent
    else:
        raise HookDenied(f"nstack role {role_id} must run on the {role.agent} agent; set {agent_key} to it.")

    new_args.pop("model", None)
    if seat["model"] != INHERIT:
        new_args["model"] = seat["model"]
    effort_key = EFFORT_KEY.get(client)
    if effort_key:
        new_args.pop(effort_key, None)
        if seat.get("effort"):
            new_args[effort_key] = seat["effort"]

    prompt_key = PROMPT_KEY[client]
    prompt = new_args.get(prompt_key)
    if not isinstance(prompt, str):
        raise HookDenied(f"nstack launch has no '{prompt_key}' text to carry the brief.")
    kept = [line for line in prompt.splitlines() if not line.startswith(FOOTER_TAG)]
    footer = [
        f"{FOOTER_TAG} role={role_id} seat={seat_no} agent={role.agent} model={seat['model']} "
        f"effort={seat.get('effort') or 'default'} source={source}",
        *(f"{FOOTER_TAG} Read first: {path}" for path in read_first(role_id)),
    ]
    new_args[prompt_key] = "\n".join(kept).rstrip() + "\n\n" + "\n".join(footer) + "\n"
    return new_args


def hook_output(client: str, *, args: dict | None = None, reason: str | None = None) -> dict:
    decision = "deny" if reason is not None else "allow"
    if client == "copilot":
        out = {"permissionDecision": decision}
        if reason is not None:
            out["permissionDecisionReason"] = reason
        else:
            out["modifiedArgs"] = args
        return out
    inner = {"hookEventName": "PreToolUse", "permissionDecision": decision}
    if reason is not None:
        inner["permissionDecisionReason"] = reason
    else:
        inner["updatedInput"] = args
    return {"hookSpecificOutput": inner}


def run_hook(stdin_text: str) -> dict | None:
    """Return the hook's JSON output, or None to let the launch through untouched."""
    try:
        data = json.loads(stdin_text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        client, _version = detect_distribution()
    except NstackError:
        return None
    tool = data.get("toolName") if "toolName" in data else data.get("tool_name")
    if not is_spawn_tool(client, tool):
        return None
    args = data.get("toolArgs") if "toolArgs" in data else data.get("tool_input")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return None
    if not isinstance(args, dict):
        return None

    match = find_marker(client, args)
    if match is None:
        agent = args.get(AGENT_KEY[client])
        if isinstance(agent, str) and agent.rpartition(":")[2] in NSTACK_AGENTS:
            return hook_output(
                client,
                reason=(
                    f"Launches of {agent} need an nstack marker such as [nstack role=implementer seat=1] "
                    "at the start of the description, so the configured model can be applied."
                ),
            )
        return None

    role_id, seat_text = match.group(1), match.group(2) or "1"
    if not seat_text.isdigit():
        return hook_output(client, reason=f"nstack marker seat must be a number, got '{seat_text}'.")
    try:
        new_args = rewrite_launch(client, args, role_id, int(seat_text))
    except HookDenied as exc:
        return hook_output(client, reason=str(exc))
    except Exception as exc:  # noqa: BLE001 - nstack launches fail loudly, never silently
        return hook_output(client, reason=f"nstack hook error for role {role_id}: {exc!r}")
    return hook_output(client, args=new_args)


def panel_context(client: str) -> str:
    """One short context line per session: each panel role's seats and models."""
    try:
        overrides = client_overrides(load_state(), client)
    except NstackError as exc:
        return f"nstack: the model configuration is invalid ({exc.message}). Run setup-nstack before delegating."
    parts = []
    for role_id, role in ROLES.items():
        if not role.panel:
            continue
        seats, _source = effective_seats(client, overrides, role_id)
        listed = ", ".join(
            f"{n}: {seat['model']}" + (f" {seat['effort']}" if seat.get("effort") else "")
            for n, seat in enumerate(seats, start=1)
        )
        parts.append(f"{role_id} {len(seats)} seat{'s' if len(seats) != 1 else ''} ({listed})")
    return "nstack panels (reference for nstack skills; no action needed): " + "; ".join(parts) + "."


def session_start_output(client: str, context: str) -> dict:
    if client == "copilot":
        return {"additionalContext": context}
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}


def viewer_context() -> str:
    """Viewer startup has its own bound and cannot suppress the model context."""
    if os.environ.get("NSTACK_VIEWER", "").lower() == "off":
        return "nstack viewer hook startup is disabled by NSTACK_VIEWER=off. Explicit viewer ensure/open commands still work."
    node = shutil.which("node")
    if node is None:
        return "nstack viewer warning (node_missing). Node >=20 is not on PATH. Install Node >=20 and run the viewer ensure command. Model configuration remains available."
    viewer = SCRIPT_DIR / "viewer" / "viewer.mjs"
    if not viewer.is_file():
        return f"nstack viewer warning (viewer_missing). The viewer bundle is missing at {viewer}. Reinstall the nstack plugin. Model configuration remains available."
    try:
        result = subprocess.run(
            [node, str(viewer), "ensure"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=7.5,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "nstack viewer warning (startup_timeout). Viewer ensure exceeded the 7.5 second hook bound. Run the viewer ensure command to inspect its owner and retry. The hook stopped its own ensure command. No existing viewer or unrelated process was signalled. Model configuration remains available."
    except OSError as exc:
        return f"nstack viewer warning (node_failed). {exc}. Check Node >=20 and plugin file permissions, then run viewer ensure. Model configuration remains available."
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "nstack viewer warning (invalid_output). Viewer ensure did not return JSON. Check the Node installation and viewer bundle, then run ensure manually. Model configuration remains available."
    ready_url = data.get("url") if isinstance(data, dict) else None
    match = re.fullmatch(r"http://127\.0\.0\.1:([0-9]{1,5})", ready_url) if isinstance(ready_url, str) else None
    if (
        result.returncode == 0
        and isinstance(data, dict)
        and data.get("ok") is True
        and match
        and 1 <= int(match.group(1)) <= 65535
        and data.get("protocol") == 1
        and type(data.get("pid")) is int
        and data["pid"] > 0
        and isinstance(data.get("buildId"), str)
        and re.fullmatch(r"[a-f0-9]{24}", data["buildId"])
    ):
        return f"nstack viewer ready at {data['url']}. Use the shared viewer open command to publish an MDX document. Published documents and feedback remain on this device."
    errors = data.get("errors") if isinstance(data, dict) else None
    failure = errors[0] if isinstance(errors, list) and errors and isinstance(errors[0], dict) else {}
    return (
        f"nstack viewer warning ({failure.get('code', 'ensure_failed')}). "
        f"{failure.get('message', 'Viewer ensure did not prove readiness.')} "
        f"{failure.get('repair', 'Run viewer ensure manually and inspect its diagnostics.')} "
        "Model configuration remains available."
    )


def cmd_session_start() -> int:
    try:
        sys.stdin.read()
        client, _version = detect_distribution()
        context = panel_context(client)
        try:
            viewer = viewer_context()
        except Exception as exc:  # noqa: BLE001 - diagnostics preserve the independent model context
            viewer = f"nstack viewer warning (viewer_error). {exc}. Run viewer ensure manually to inspect its diagnostics. Model configuration remains available."
        output = session_start_output(client, context + "\n" + viewer)
    except Exception:  # noqa: BLE001 - a hook must never break session start
        output = None
    if output is not None:
        sys.stdout.write(json.dumps(output))
    return 0


def cmd_hook() -> int:
    try:
        output = run_hook(sys.stdin.read())
    except Exception:  # noqa: BLE001 - a hook crash must never block unrelated launches
        output = None
    if output is not None:
        sys.stdout.write(json.dumps(output))
    return 0


# --- entry point ----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nstack_config.py", description="nstack model management")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("roles", help="print the role catalog and built-in defaults")
    sub.add_parser("status", help="print the effective model per role and seat (read-only)")

    configure = sub.add_parser("configure", help="preview or apply model overrides")
    configure.add_argument("--input", required=True, help="JSON file with role overrides")
    mode = configure.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="preview changes without writing")
    mode.add_argument("--apply", action="store_true", help="apply a previewed plan")
    configure.add_argument("--plan-id", default="", help="plan id from the preview (required with --apply)")

    verify = sub.add_parser("record-verification", help="record what the client showed for a dispatch probe")
    verify.add_argument("--role", required=True)
    verify.add_argument("--seat", type=int, default=1)
    verify.add_argument("--status", required=True, choices=("verified", "failed"))
    verify.add_argument("--evidence", required=True)

    sub.add_parser("hook", help="pre-tool hook; reads the client's payload on stdin")
    sub.add_parser("session-start", help="session-start hook; prints the panel context")
    return parser


COMMANDS = {
    "roles": cmd_roles,
    "status": cmd_status,
    "configure": cmd_configure,
    "record-verification": cmd_record_verification,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "hook":
        return cmd_hook()
    if args.command == "session-start":
        return cmd_session_start()
    try:
        result = COMMANDS[args.command](args)
    except NstackError as exc:
        print(json.dumps({"ok": False, "errors": [exc.as_dict()]}, indent=2, ensure_ascii=False))
        return exc.exit_code
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())

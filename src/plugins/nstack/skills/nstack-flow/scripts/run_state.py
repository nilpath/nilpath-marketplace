#!/usr/bin/env python3
"""Local, transactional run accounting. Python 3.11+, standard library only."""

from __future__ import annotations

import sys

if sys.version_info < (3, 11):  # pragma: no cover
    sys.stdout.write('{"ok":false,"error":{"code":"unsupported_python","message":"Python 3.11+ required."}}\n')
    sys.exit(1)

import argparse
import errno
import hashlib
import json
import os
import re
import sqlite3
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias, TypedDict


class StateError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise StateError(code, message)


def obj(value: object, required: str, optional: str = "") -> dict:
    require(type(value) is dict, "invalid_request", "Expected an object.")
    keys = set(value)
    need = set(required.split())
    require(need <= keys and keys <= need | set(optional.split()),
            "invalid_request", f"Expected fields {required}; optional fields {optional}.")
    return value


def text(value: object) -> str:
    require(isinstance(value, str) and bool(value.strip()) and "\x00" not in value,
            "invalid_request", "Expected a nonempty string without NUL.")
    return value


def identifier(value: object) -> str:
    value = text(value)
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value) is not None,
            "invalid_request", "IDs must be 1-128 ASCII letters, digits, dots, underscores, or hyphens.")
    return value


def digest(value: object) -> str:
    value = text(value)
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None,
            "invalid_request", "Expected sha256: followed by 64 lowercase hex digits.")
    return value


def number(value: object) -> int:
    require(type(value) is int and value >= 0, "invalid_request", "Expected a nonnegative integer.")
    return value


def sequence(value: object, parser) -> tuple:
    require(type(value) is list, "invalid_request", "Expected an array.")
    return tuple(parser(item) for item in value)


def strings(value: object) -> tuple[str, ...]:
    result = sequence(value, identifier)
    require(len(set(result)) == len(result), "invalid_request", "Duplicate IDs in an array.")
    return result


def choice(value: object, choices: tuple[str, ...]) -> str:
    require(value in choices, "invalid_request", f"Expected one of {choices}.")
    return value


def canonical(value: object, *, live: bool = True) -> str:
    path = Path(text(value))
    require(path.is_absolute(), "invalid_request", "Paths must be absolute.")
    if not live:
        require(str(path) == value and os.path.normpath(value) == value,
                "invalid_request", "Stored paths must be normalized absolute identities.")
        return value
    try:
        try:
            return str(path.resolve(strict=True))
        except FileNotFoundError:
            return str(path.resolve())
    except RuntimeError as exc:
        raise StateError("invalid_request", "Path contains a symlink loop.") from exc
    except OSError as exc:
        if exc.errno != errno.ELOOP:
            raise
        raise StateError("invalid_request", "Path contains a symlink loop.") from exc


def overlaps(a: str, b: str) -> bool:
    x, y = Path(a), Path(b)
    return x == y or x in y.parents or y in x.parents


def encoded(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise StateError("invalid_request", "Value cannot be encoded as finite JSON.") from exc


def fingerprint(value: object) -> str:
    return "sha256:" + hashlib.sha256(encoded(value).encode()).hexdigest()


@dataclass(frozen=True)
class SourceRef:
    path_or_url: str
    exact_locator: str
    content_digest: str | None = None


def parse_source(value: object) -> SourceRef:
    d = obj(value, "path_or_url exact_locator", "content_digest")
    return SourceRef(text(d["path_or_url"]), text(d["exact_locator"]),
                     digest(d["content_digest"]) if d.get("content_digest") is not None else None)


@dataclass(frozen=True)
class EvidenceRef:
    path: str
    content_digest: str | None = None


def parse_evidence(value: object, *, live: bool = True) -> EvidenceRef:
    d = obj(value, "path", "content_digest")
    return EvidenceRef(canonical(d["path"], live=live),
                       digest(d["content_digest"]) if d.get("content_digest") is not None else None)


def evidence_digest(ref: EvidenceRef) -> str:
    path = Path(ref.path)
    require(path.is_file(), "invalid_evidence", f"Evidence is not a local file: {path}.")
    with path.open("rb") as stream:
        hasher = hashlib.sha256()
        size = 0
        for block in iter(lambda: stream.read(65536), b""):
            size += len(block)
            hasher.update(block)
    require(size > 0, "invalid_evidence", f"Evidence file is empty: {path}.")
    return "sha256:" + hasher.hexdigest()


def bind_evidence(refs: tuple[EvidenceRef, ...]) -> tuple[EvidenceRef, ...]:
    require(bool(refs), "invalid_evidence", "At least one local evidence file is required.")
    result = []
    for ref in refs:
        actual = evidence_digest(ref)
        require(ref.content_digest in (None, actual), "invalid_evidence",
                f"Evidence digest does not match: {ref.path}.")
        result.append(EvidenceRef(ref.path, actual))
    return tuple(result)


def evidence_fresh(refs: tuple[EvidenceRef, ...]) -> bool:
    for ref in refs:
        if path_state(ref.path) != "unchanged":
            return False
        try:
            if evidence_digest(ref) != ref.content_digest:
                return False
        except StateError as exc:
            if exc.code != "invalid_evidence":
                raise
            return False
        except FileNotFoundError:
            return False
    return bool(refs)


@dataclass(frozen=True)
class Workspace:
    repo_identity: str
    canonical_path: str
    branch: str
    head: str
    dirty_digest: str


def parse_workspace(value: object, *, live: bool = True) -> Workspace:
    d = obj(value, "repo_identity canonical_path branch head dirty_digest")
    return Workspace(text(d["repo_identity"]), canonical(d["canonical_path"], live=live),
                     text(d["branch"]), text(d["head"]), digest(d["dirty_digest"]))


def same_identity(a: Workspace, b: Workspace) -> bool:
    return (a.repo_identity, a.canonical_path, a.branch) == (b.repo_identity, b.canonical_path, b.branch)


@dataclass(frozen=True)
class Unit:
    stable_id: str
    definition_digest: str
    dependencies: tuple[str, ...]
    acceptance: str
    exclusive_output: str
    source_refs: tuple[SourceRef, ...]


def parse_unit(value: object, *, live: bool = True) -> Unit:
    d = obj(value, "stable_id definition_digest dependencies acceptance exclusive_output source_refs")
    return Unit(identifier(d["stable_id"]), digest(d["definition_digest"]), strings(d["dependencies"]),
                text(d["acceptance"]), canonical(d["exclusive_output"], live=live),
                sequence(d["source_refs"], parse_source))


@dataclass(frozen=True)
class Plan:
    plan_ref: SourceRef
    units: tuple[Unit, ...]


def validate_plan(plan: Plan) -> None:
    units = {u.stable_id: u for u in plan.units}
    require(len(units) == len(plan.units), "invalid_plan", "Unit IDs must be unique.")
    pending = {key: len(unit.dependencies) for key, unit in units.items()}
    downstream: dict[str, list[str]] = {key: [] for key in units}
    for unit in plan.units:
        for dependency in unit.dependencies:
            require(dependency in units, "invalid_plan", f"Missing dependency {dependency}.")
            downstream[dependency].append(unit.stable_id)
    ready = [key for key, count in pending.items() if count == 0]
    visited = 0
    while ready:
        key = ready.pop()
        visited += 1
        for child in downstream[key]:
            pending[child] -= 1
            if pending[child] == 0:
                ready.append(child)
    require(visited == len(units), "invalid_plan", "The dependency graph contains a cycle.")
    for i, unit in enumerate(plan.units):
        for other in plan.units[i + 1:]:
            require(not overlaps(unit.exclusive_output, other.exclusive_output),
                    "output_conflict", f"Unit outputs overlap: {unit.stable_id}, {other.stable_id}.")


def parse_plan(value: object, *, live: bool = True) -> Plan:
    d = obj(value, "plan_ref units")
    plan = Plan(parse_source(d["plan_ref"]), sequence(d["units"], lambda u: parse_unit(u, live=live)))
    validate_plan(plan)
    return plan


@dataclass(frozen=True)
class CoordinatorContext:
    workspace: Workspace
    protected_roots: tuple[str, ...]
    source_refs: tuple[SourceRef, ...]
    conversation_locator: str | None = None
    budget_ref: SourceRef | None = None
    decision_trail_ref: SourceRef | None = None


def parse_context(value: object, *, live: bool = True) -> CoordinatorContext:
    d = obj(value, "workspace protected_roots source_refs",
            "conversation_locator budget_ref decision_trail_ref")
    roots = sequence(d["protected_roots"], lambda p: canonical(p, live=live))
    require(bool(roots) and len(set(roots)) == len(roots),
            "invalid_request", "Protected roots must be nonempty and unique.")
    return CoordinatorContext(
        parse_workspace(d["workspace"], live=live), roots, sequence(d["source_refs"], parse_source),
        text(d["conversation_locator"]) if d.get("conversation_locator") is not None else None,
        parse_source(d["budget_ref"]) if d.get("budget_ref") is not None else None,
        parse_source(d["decision_trail_ref"]) if d.get("decision_trail_ref") is not None else None,
    )


WorkerState: TypeAlias = Literal["running", "finished", "stopped", "unknown"]


@dataclass(frozen=True)
class WorkerObservation:
    attempt_id: str
    state: WorkerState
    evidence_refs: tuple[EvidenceRef, ...]
    native_handle: str | None = None


def parse_worker(value: object) -> WorkerObservation:
    d = obj(value, "attempt_id state evidence_refs", "native_handle")
    return WorkerObservation(identifier(d["attempt_id"]),
                             choice(d["state"], ("running", "finished", "stopped", "unknown")),
                             sequence(d["evidence_refs"], parse_evidence),
                             text(d["native_handle"]) if d.get("native_handle") is not None else None)


@dataclass(frozen=True)
class Observations:
    workspace: Workspace
    workers: tuple[WorkerObservation, ...] = ()


def parse_observations(value: object) -> Observations:
    d = obj(value, "workspace", "workers")
    workers = sequence(d.get("workers", []), parse_worker)
    require(len({w.attempt_id for w in workers}) == len(workers),
            "invalid_request", "Duplicate worker observations.")
    return Observations(parse_workspace(d["workspace"]), workers)


@dataclass(frozen=True)
class ReplacePlan:
    plan: Plan
    supersedes: tuple[str, ...]


@dataclass(frozen=True)
class ReserveAttempt:
    attempt_id: str
    unit_id: str
    input_receipts: tuple[str, ...]
    brief_ref: SourceRef
    output_location: str
    observations: Observations


@dataclass(frozen=True)
class RecordWorker:
    observation: WorkerObservation


@dataclass(frozen=True)
class AbandonAttempt:
    attempt_id: str
    evidence_refs: tuple[EvidenceRef, ...]


@dataclass(frozen=True)
class RecordReceipt:
    receipt_id: str
    unit_id: str
    attempt_id: str
    workspace: Workspace
    input_receipts: tuple[str, ...]
    verifier: str
    verdict: Literal["pass", "fail"]
    evidence_refs: tuple[EvidenceRef, ...]
    observations: Observations
    acceptance_receipts: tuple[str, ...] | None = None
    reverifies: str | None = None


@dataclass(frozen=True)
class PrepareEffect:
    operation_id: str
    kind: Literal["push", "reply", "resolve_thread", "rerun", "remove"]
    exact_target: str
    expected_fingerprint: str
    source_refs: tuple[SourceRef, ...]


@dataclass(frozen=True)
class ResolveEffect:
    operation_id: str
    state: Literal["confirmed", "unknown", "not_occurred"]
    evidence_refs: tuple[EvidenceRef, ...]


@dataclass(frozen=True)
class Pause:
    source_refs: tuple[SourceRef, ...]
    next_route: str
    observations: Observations | None = None


@dataclass(frozen=True)
class Adopt:
    source_refs: tuple[SourceRef, ...]
    next_route: str
    conversation_locator: str | None = None
    observations: Observations | None = None


@dataclass(frozen=True)
class Resume:
    observations: Observations


Change: TypeAlias = ReplacePlan | ReserveAttempt | RecordWorker | AbandonAttempt | RecordReceipt | PrepareEffect | ResolveEffect | Pause | Adopt | Resume


def parse_change(value: object) -> Change:
    require(type(value) is dict and "type" in value, "invalid_request", "A change requires its type.")
    match value["type"]:
        case "replace_plan":
            d = obj(value, "type plan supersedes")
            return ReplacePlan(parse_plan(d["plan"]), strings(d["supersedes"]))
        case "reserve_attempt":
            d = obj(value, "type attempt_id unit_id input_receipts brief_ref output_location observations")
            return ReserveAttempt(identifier(d["attempt_id"]), identifier(d["unit_id"]),
                                  strings(d["input_receipts"]), parse_source(d["brief_ref"]),
                                  canonical(d["output_location"]), parse_observations(d["observations"]))
        case "record_worker":
            d = obj(value, "type observation")
            return RecordWorker(parse_worker(d["observation"]))
        case "abandon_attempt":
            d = obj(value, "type attempt_id evidence_refs")
            return AbandonAttempt(identifier(d["attempt_id"]), sequence(d["evidence_refs"], parse_evidence))
        case "record_receipt":
            d = obj(value, "type receipt_id unit_id attempt_id workspace input_receipts verifier verdict evidence_refs observations",
                    "acceptance_receipts reverifies")
            return RecordReceipt(identifier(d["receipt_id"]), identifier(d["unit_id"]),
                                 identifier(d["attempt_id"]), parse_workspace(d["workspace"]),
                                 strings(d["input_receipts"]), text(d["verifier"]),
                                 choice(d["verdict"], ("pass", "fail")),
                                 sequence(d["evidence_refs"], parse_evidence), parse_observations(d["observations"]),
                                 strings(d["acceptance_receipts"]) if d.get("acceptance_receipts") is not None else None,
                                 identifier(d["reverifies"]) if d.get("reverifies") is not None else None)
        case "prepare_effect":
            d = obj(value, "type operation_id kind exact_target expected_fingerprint source_refs")
            return PrepareEffect(identifier(d["operation_id"]), choice(d["kind"], ("push", "reply", "resolve_thread", "rerun", "remove")),
                                 text(d["exact_target"]), text(d["expected_fingerprint"]),
                                 sequence(d["source_refs"], parse_source))
        case "resolve_effect":
            d = obj(value, "type operation_id state evidence_refs")
            return ResolveEffect(identifier(d["operation_id"]), choice(d["state"], ("confirmed", "unknown", "not_occurred")),
                                 sequence(d["evidence_refs"], parse_evidence))
        case "pause":
            d = obj(value, "type source_refs next_route", "observations")
            return Pause(sequence(d["source_refs"], parse_source), text(d["next_route"]),
                         parse_observations(d["observations"]) if d.get("observations") is not None else None)
        case "adopt":
            d = obj(value, "type source_refs next_route", "conversation_locator observations")
            return Adopt(sequence(d["source_refs"], parse_source), text(d["next_route"]),
                         text(d["conversation_locator"]) if d.get("conversation_locator") is not None else None,
                         parse_observations(d["observations"]) if d.get("observations") is not None else None)
        case "resume":
            d = obj(value, "type observations")
            return Resume(parse_observations(d["observations"]))
        case _:
            raise StateError("invalid_request", "Unknown change type.")


@dataclass
class Attempt:
    attempt_id: str
    unit_id: str
    unit_fingerprint: str
    input_receipts: tuple[str, ...]
    brief_ref: SourceRef
    output_location: str
    workspace: Workspace
    state: Literal["reserved", "running", "finished", "stopped", "unknown", "abandoned"] = "reserved"
    native_handle: str | None = None
    evidence_refs: tuple[EvidenceRef, ...] = ()
    receipt_id: str | None = None
    finished_observed: bool = False
    finished_evidence_refs: tuple[EvidenceRef, ...] = ()

    def held(self) -> bool:
        return (self.receipt_id is None and self.state != "abandoned"
                and (self.finished_observed or self.state != "stopped"))


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    unit_id: str
    attempt_id: str
    unit_fingerprint: str
    workspace: Workspace
    input_receipts: tuple[str, ...]
    verifier: str
    verdict: Literal["pass", "fail"]
    evidence_refs: tuple[EvidenceRef, ...]
    revision: int
    acceptance_receipts: tuple[str, ...]
    reverifies: str | None


@dataclass
class Effect:
    operation_id: str
    kind: Literal["push", "reply", "resolve_thread", "rerun", "remove"]
    exact_target: str
    expected_fingerprint: str
    source_refs: tuple[SourceRef, ...]
    state: Literal["prepared", "confirmed", "unknown", "not_occurred"] = "prepared"
    evidence_refs: tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True)
class Handoff:
    revision: int
    previous_owner: str
    owner_nonce: str
    reason: Literal["pause", "adopt"]
    source_refs: tuple[SourceRef, ...]
    next_route: str


@dataclass
class Run:
    run_uuid: str
    owner_nonce: str
    revision: int
    context: CoordinatorContext
    plan: Plan
    paused: bool = False
    plan_history: list[Plan] = field(default_factory=list)
    attempts: dict[str, Attempt] = field(default_factory=dict)
    receipts: dict[str, Receipt] = field(default_factory=dict)
    effects: dict[str, Effect] = field(default_factory=dict)
    handoffs: list[Handoff] = field(default_factory=list)
    superseded_receipts: list[str] = field(default_factory=list)


def parse_run(value: object) -> Run:
    d = obj(value, "run_uuid owner_nonce revision context plan paused plan_history attempts receipts effects handoffs superseded_receipts")
    require(type(d["paused"]) is bool, "invalid_request", "Expected a boolean paused field.")
    run = Run(identifier(d["run_uuid"]), identifier(d["owner_nonce"]), number(d["revision"]),
              parse_context(d["context"], live=False), parse_plan(d["plan"], live=False), d["paused"],
              list(sequence(d["plan_history"], lambda p: parse_plan(p, live=False))))
    for key in ("attempts", "receipts", "effects"):
        require(type(d[key]) is dict, "invalid_request", f"Expected an object for {key}.")
    for key, value in d["attempts"].items():
        a = obj(value, "attempt_id unit_id unit_fingerprint input_receipts brief_ref output_location workspace state native_handle evidence_refs receipt_id finished_observed finished_evidence_refs")
        require(key == a["attempt_id"], "invalid_request", "Attempt key mismatch.")
        require(type(a["finished_observed"]) is bool, "invalid_request", "Expected a boolean finished observation.")
        run.attempts[key] = Attempt(
            identifier(a["attempt_id"]), identifier(a["unit_id"]), digest(a["unit_fingerprint"]),
            strings(a["input_receipts"]), parse_source(a["brief_ref"]), canonical(a["output_location"], live=False),
            parse_workspace(a["workspace"], live=False), choice(a["state"], ("reserved", "running", "finished", "stopped", "unknown", "abandoned")),
            text(a["native_handle"]) if a["native_handle"] is not None else None,
            sequence(a["evidence_refs"], lambda r: parse_evidence(r, live=False)),
            identifier(a["receipt_id"]) if a["receipt_id"] is not None else None, a["finished_observed"],
            sequence(a["finished_evidence_refs"], lambda r: parse_evidence(r, live=False)))
    for key, value in d["receipts"].items():
        r = obj(value, "receipt_id unit_id attempt_id unit_fingerprint workspace input_receipts verifier verdict evidence_refs revision acceptance_receipts reverifies")
        require(key == r["receipt_id"], "invalid_request", "Receipt key mismatch.")
        run.receipts[key] = Receipt(identifier(r["receipt_id"]), identifier(r["unit_id"]), identifier(r["attempt_id"]),
                                    digest(r["unit_fingerprint"]), parse_workspace(r["workspace"], live=False),
                                    strings(r["input_receipts"]), text(r["verifier"]), choice(r["verdict"], ("pass", "fail")),
                                    sequence(r["evidence_refs"], lambda ref: parse_evidence(ref, live=False)), number(r["revision"]),
                                    strings(r["acceptance_receipts"]),
                                    identifier(r["reverifies"]) if r["reverifies"] is not None else None)
    for key, value in d["effects"].items():
        e = obj(value, "operation_id kind exact_target expected_fingerprint source_refs state evidence_refs")
        require(key == e["operation_id"], "invalid_request", "Effect key mismatch.")
        run.effects[key] = Effect(identifier(e["operation_id"]), choice(e["kind"], ("push", "reply", "resolve_thread", "rerun", "remove")),
                                  text(e["exact_target"]), text(e["expected_fingerprint"]),
                                  sequence(e["source_refs"], parse_source), choice(e["state"], ("prepared", "confirmed", "unknown", "not_occurred")),
                                  sequence(e["evidence_refs"], lambda r: parse_evidence(r, live=False)))
    for value in sequence(d["handoffs"], lambda x: x):
        h = obj(value, "revision previous_owner owner_nonce reason source_refs next_route")
        run.handoffs.append(Handoff(number(h["revision"]), identifier(h["previous_owner"]), identifier(h["owner_nonce"]),
                                   choice(h["reason"], ("pause", "adopt")), sequence(h["source_refs"], parse_source),
                                   text(h["next_route"])))
    for attempt in run.attempts.values():
        require(attempt.finished_observed == bool(attempt.finished_evidence_refs)
                and (attempt.state != "finished" or attempt.finished_observed)
                and (not attempt.finished_observed or attempt.state in ("finished", "stopped", "unknown", "abandoned"))
                and all(r.content_digest is not None for r in attempt.finished_evidence_refs),
                "invalid_request", "Finished observation history is inconsistent.")
        require(all(r.content_digest is not None for r in attempt.evidence_refs),
                "invalid_request", "Stored worker evidence must bind content digests.")
        require(attempt.state != "abandoned" or (
                attempt.finished_observed and bool(attempt.evidence_refs) and attempt.receipt_id is None),
                "invalid_request", "Abandoned work must retain finished history and explicit retirement evidence.")
        definitions = [u for p in (*run.plan_history, run.plan) for u in p.units
                       if u.stable_id == attempt.unit_id and fingerprint(asdict(u)) == attempt.unit_fingerprint]
        require(bool(definitions), "invalid_request", "Attempt has no matching unit definition.")
        definition = definitions[-1]
        require(same_identity(attempt.workspace, run.context.workspace)
                and (Path(attempt.output_location) == Path(definition.exclusive_output)
                     or Path(definition.exclusive_output) in Path(attempt.output_location).parents),
                "invalid_request", "Attempt workspace or output does not match its definition.")
        require(attempt.receipt_id is None or attempt.receipt_id in run.receipts,
                "invalid_request", "Dangling attempt receipt.")
        require(all(r in run.receipts for r in attempt.input_receipts), "invalid_request", "Dangling attempt input.")
        require({run.receipts[r].unit_id for r in attempt.input_receipts} == set(definition.dependencies)
                and len(attempt.input_receipts) == len(definition.dependencies),
                "invalid_request", "Attempt inputs do not match its dependency definition.")
        if attempt.held():
            current = next((u for u in run.plan.units if u.stable_id == attempt.unit_id), None)
            require(current == definition, "invalid_request", "Held attempt has a superseded unit.")
    for receipt in run.receipts.values():
        attempt = run.attempts.get(receipt.attempt_id)
        require(attempt is not None and attempt.receipt_id is not None
                and attempt.unit_id == receipt.unit_id and attempt.input_receipts == receipt.input_receipts
                and attempt.unit_fingerprint == receipt.unit_fingerprint and attempt.state == "finished"
                and same_identity(receipt.workspace, run.context.workspace) and bool(receipt.evidence_refs)
                and receipt.revision <= run.revision,
                "invalid_request", "Inconsistent receipt.")
        if receipt.reverifies is None:
            require(attempt.receipt_id == receipt.receipt_id,
                    "invalid_request", "Initial receipt must reconcile its attempt.")
        else:
            previous = run.receipts.get(receipt.reverifies)
            earlier = [r for r in run.receipts.values()
                       if r.unit_id == receipt.unit_id and r.revision < receipt.revision]
            require(previous is not None and previous.verdict == "pass"
                    and previous == max(earlier, key=lambda r: r.revision, default=None)
                    and receipt_follows(run, receipt.receipt_id, attempt.receipt_id),
                    "invalid_request", "Invalid re-verification history.")
        require(all(r in run.receipts and run.receipts[r].revision < receipt.revision
                    and run.receipts[r].verdict == "pass"
                    for r in (*receipt.input_receipts, *receipt.acceptance_receipts)),
                "invalid_request", "Invalid receipt dependency history.")
        if receipt.verdict == "pass" or receipt.acceptance_receipts:
            require(inputs_follow(run, receipt.input_receipts, receipt.acceptance_receipts)
                    and all(run.receipts[r].workspace == receipt.workspace for r in receipt.acceptance_receipts),
                    "invalid_request", "Acceptance receipts changed dispatched lineage or verified snapshot.")
        require(all(r.content_digest is not None for r in receipt.evidence_refs),
                "invalid_request", "Stored evidence must bind content digests.")
    run.superseded_receipts = list(strings(d["superseded_receipts"]))
    require(set(run.superseded_receipts) <= set(run.receipts), "invalid_request", "Dangling superseded proof.")
    held = [a for a in run.attempts.values() if a.held()]
    require(all(not overlaps(a.output_location, b.output_location)
                for i, a in enumerate(held) for b in held[i + 1:]),
            "invalid_request", "Stored reservations overlap.")
    for effect in run.effects.values():
        require(effect.state in ("prepared", "unknown") or bool(effect.evidence_refs),
                "invalid_request", "Resolved effect lacks evidence.")
        require(all(r.content_digest is not None for r in effect.evidence_refs),
                "invalid_request", "Stored effect evidence lacks content digests.")
    return run


def receipt_follows(run: Run, receipt_id: str, original_id: str) -> bool:
    """Follow only explicit, causal re-verifications of the same dispatched attempt."""
    original = run.receipts.get(original_id)
    cursor = run.receipts.get(receipt_id)
    if original is None:
        return False
    while cursor is not None:
        if (cursor.unit_id, cursor.attempt_id, cursor.unit_fingerprint, cursor.input_receipts) != (
                original.unit_id, original.attempt_id, original.unit_fingerprint, original.input_receipts):
            return False
        if cursor.receipt_id == original_id:
            return True
        previous = run.receipts.get(cursor.reverifies)
        if previous is None or previous.revision >= cursor.revision:
            return False
        cursor = previous
    return False


def inputs_follow(run: Run, dispatched: tuple[str, ...], accepted: tuple[str, ...]) -> bool:
    if len(dispatched) != len(accepted) or not all(r in run.receipts for r in (*dispatched, *accepted)):
        return False
    refreshed = {run.receipts[r].unit_id: r for r in accepted}
    return len(refreshed) == len(accepted) and all(
        run.receipts[r].unit_id in refreshed and receipt_follows(run, refreshed[run.receipts[r].unit_id], r)
        for r in dispatched)


def latest_receipt(run: Run, unit_id: str) -> Receipt | None:
    return max((r for r in run.receipts.values() if r.unit_id == unit_id), key=lambda r: r.revision, default=None)


def protected_store(store: Path, context: CoordinatorContext, plan: Plan) -> None:
    roots = (*context.protected_roots, context.workspace.canonical_path,
             *(u.exclusive_output for u in plan.units))
    require(all(not overlaps(str(store.parent), root) for root in roots),
            "unsafe_store", "The store directory must be disjoint from product, output, and cleanup roots.")


def path_state(path: str) -> Literal["unchanged", "drifted", "unsafe"]:
    try:
        return "unchanged" if canonical(path) == path else "drifted"
    except (StateError, OSError):
        return "unsafe"


def unsafe_paths(run: Run) -> list[dict[str, str]]:
    paths = {run.context.workspace.canonical_path, *run.context.protected_roots,
             *(u.exclusive_output for u in run.plan.units),
             *(a.output_location for a in run.attempts.values() if a.held())}
    result = []
    for path in sorted(paths):
        status = path_state(path)
        if status != "unchanged":
            result.append({"path": path, "state": status})
    return result


def require_stable_paths(run: Run) -> None:
    require(not unsafe_paths(run), "unsafe_path", "Live paths drifted from stored identity; reconcile them before new work.")


def check_observations(run: Run, observations: Observations) -> Observations:
    require(same_identity(run.context.workspace, observations.workspace),
            "workspace_mismatch", "Observation repository, workspace path, or branch differs from the run.")
    require(Path(observations.workspace.canonical_path).is_dir(),
            "workspace_mismatch", "Observed workspace does not exist.")
    workers = []
    for worker in observations.workers:
        require(worker.attempt_id in run.attempts, "unknown_attempt", "Observation names an unknown attempt.")
        attempt = run.attempts[worker.attempt_id]
        require(attempt.native_handle is None or worker.native_handle in (None, attempt.native_handle),
                "worker_mismatch", "Observed native worker identity differs from the attempt.")
        require(worker.state != "running" or not attempt.finished_observed and attempt.state != "stopped",
                "invalid_transition", "Running observation contradicts a finished or stopped attempt.")
        refs = bind_evidence(worker.evidence_refs) if worker.state != "unknown" or worker.evidence_refs else ()
        workers.append(WorkerObservation(worker.attempt_id, worker.state, refs, worker.native_handle))
    return Observations(observations.workspace, tuple(workers))


def fresh_receipts(run: Run, observations: Observations | None) -> dict[str, str]:
    if observations is None:
        return {}
    check_observations(run, observations)
    if unsafe_paths(run):
        return {}
    current: dict[str, str] = {}
    units = {u.stable_id: u for u in run.plan.units}
    remaining = set(units)
    while remaining:
        progressed = False
        for unit_id in tuple(remaining):
            unit = units[unit_id]
            if any(dep in remaining for dep in unit.dependencies):
                continue
            remaining.remove(unit_id)
            progressed = True
            receipt = latest_receipt(run, unit_id)
            # A later failed or stale proof must not resurrect an earlier pass.
            if receipt is None:
                continue
            if (receipt.verdict == "pass" and receipt.receipt_id not in run.superseded_receipts
                    and receipt.unit_fingerprint == fingerprint(asdict(unit))
                    and receipt.workspace == observations.workspace and evidence_fresh(receipt.evidence_refs)
                    and path_state(run.attempts[receipt.attempt_id].output_location) == "unchanged"
                    and not any(a.unit_id == unit_id and a.held() for a in run.attempts.values())
                    and all(dep in current for dep in unit.dependencies)
                    and set(receipt.acceptance_receipts) == {current[dep] for dep in unit.dependencies}):
                current[unit_id] = receipt.receipt_id
        require(progressed, "store_corrupt", "Stored plan graph is invalid.")
    return current


def unit_for(run: Run, unit_id: str) -> Unit:
    unit = next((u for u in run.plan.units if u.stable_id == unit_id), None)
    require(unit is not None, "unknown_unit", f"Unknown current unit {unit_id}.")
    return unit


def attempt_for(run: Run, attempt_id: str) -> Attempt:
    require(attempt_id in run.attempts, "unknown_attempt", f"Unknown attempt {attempt_id}.")
    return run.attempts[attempt_id]


def mutate(run: Run, change: Change, store: Path) -> None:
    match change:
        case ReplacePlan(plan, supersedes):
            protected_store(store, run.context, plan)
            old = {u.stable_id: u for u in run.plan.units}
            new = {u.stable_id: u for u in plan.units}
            changed = {key for key in old if new.get(key) != old[key]}
            require(set(supersedes) == changed, "supersession_required",
                    "Supersedes must name exactly the removed or changed current unit IDs.")
            retired = {u.stable_id for p in run.plan_history for u in p.units} - set(old)
            require(not (retired & (set(new) - set(old))), "supersession_required", "Retired unit IDs cannot be reused.")
            affected = set(changed)
            while True:
                downstream = {u.stable_id for u in old.values() if affected.intersection(u.dependencies)}
                if downstream <= affected:
                    break
                affected.update(downstream)
            require(not any(a.held() and a.unit_id in affected for a in run.attempts.values()),
                    "reservation_held", "Unreconciled attempts prevent replacing their unit definitions.")
            for a in run.attempts.values():
                if a.held():
                    require(all(u.stable_id == a.unit_id or not overlaps(u.exclusive_output, a.output_location)
                                for u in plan.units), "reservation_held", "Replacement conflicts with a held output.")
            run.superseded_receipts = sorted(set(run.superseded_receipts) |
                                             {r.receipt_id for r in run.receipts.values() if r.unit_id in affected})
            run.plan_history.append(run.plan)
            run.plan = plan
        case ReserveAttempt():
            require(not run.paused, "run_paused", "Resume accounting before reserving new work.")
            require_stable_paths(run)
            require(change.attempt_id not in run.attempts, "duplicate_attempt", "Attempt ID already exists.")
            unit = unit_for(run, change.unit_id)
            require(Path(change.output_location) == Path(unit.exclusive_output)
                    or Path(unit.exclusive_output) in Path(change.output_location).parents,
                    "output_conflict", "Attempt output must be contained by its unit's exclusive output.")
            require(not overlaps(change.output_location, str(store.parent)),
                    "unsafe_store", "Attempt output contains the store.")
            require(not any(a.held() and overlaps(a.output_location, change.output_location)
                            for a in run.attempts.values()), "reservation_held", "An unresolved attempt holds this output.")
            current = fresh_receipts(run, change.observations)
            require(all(dep in current for dep in unit.dependencies)
                    and set(change.input_receipts) == {current[dep] for dep in unit.dependencies},
                    "stale_inputs", "Attempt inputs must be the fresh receipts for every dependency.")
            run.attempts[change.attempt_id] = Attempt(
                change.attempt_id, change.unit_id, fingerprint(asdict(unit)), change.input_receipts,
                change.brief_ref, change.output_location, change.observations.workspace)
        case RecordWorker(observation):
            attempt = attempt_for(run, observation.attempt_id)
            require(attempt.held(), "terminal_attempt", "Attempt is already reconciled.")
            require(not attempt.finished_observed or observation.state != "running",
                    "invalid_transition", "An attempt ever observed finished cannot return to running.")
            require(not attempt.finished_observed or observation.state != "stopped",
                    "invalid_transition", "Process stop cannot discard finished work; verify it or explicitly abandon it.")
            refs = bind_evidence(observation.evidence_refs) if observation.state != "unknown" or observation.evidence_refs else ()
            if attempt.native_handle is not None and observation.native_handle is not None:
                require(attempt.native_handle == observation.native_handle,
                        "worker_mismatch", "Native worker identity changed.")
            attempt.state = observation.state
            attempt.native_handle = observation.native_handle or attempt.native_handle
            attempt.evidence_refs = refs
            if observation.state == "finished":
                attempt.finished_observed = True
                if not attempt.finished_evidence_refs:
                    attempt.finished_evidence_refs = refs
        case AbandonAttempt(attempt_id, evidence_refs):
            attempt = attempt_for(run, attempt_id)
            require(attempt.held(), "terminal_attempt", "Attempt is already reconciled.")
            require(attempt.finished_observed and attempt.state in ("finished", "stopped"),
                    "attempt_mismatch", "Abandonment requires confirmed finished work, not an unresolved worker.")
            refs = bind_evidence(evidence_refs)
            attempt.state = "abandoned"
            attempt.evidence_refs = refs
        case RecordReceipt():
            require_stable_paths(run)
            require(change.receipt_id not in run.receipts, "duplicate_receipt", "Receipt ID already exists.")
            unit = unit_for(run, change.unit_id)
            attempt = attempt_for(run, change.attempt_id)
            require(attempt.unit_id == change.unit_id and attempt.state == "finished",
                    "attempt_mismatch", "Verification requires this unit's finished attempt.")
            require(attempt.unit_fingerprint == fingerprint(asdict(unit)),
                    "attempt_mismatch", "Attempt belongs to an older unit definition.")
            if change.reverifies is None:
                require(attempt.receipt_id is None, "attempt_mismatch",
                        "An already reconciled attempt requires an explicit re-verification.")
            else:
                require(change.reverifies in run.receipts, "unknown_receipt", "Unknown re-verification receipt.")
                previous = run.receipts[change.reverifies]
                require(attempt.receipt_id is not None and previous == latest_receipt(run, change.unit_id)
                        and previous.verdict == "pass" and previous.receipt_id not in run.superseded_receipts
                        and receipt_follows(run, previous.receipt_id, attempt.receipt_id)
                        and path_state(attempt.output_location) == "unchanged",
                        "reverification_conflict", "Re-verification must extend the unit's latest unsuperseded passing attempt.")
                require(not any(a.unit_id == change.unit_id and a.held() for a in run.attempts.values()),
                        "reservation_held", "Unresolved sibling work prevents re-verification.")
            check_observations(run, change.observations)
            require(same_identity(attempt.workspace, change.workspace) and change.workspace == change.observations.workspace,
                    "workspace_mismatch", "Receipt workspace must match the attempt identity and current observation.")
            accepted = change.acceptance_receipts
            if accepted is None:
                accepted = change.input_receipts if change.verdict == "pass" else ()
            require(change.input_receipts == attempt.input_receipts, "stale_inputs",
                    "Receipt inputs must retain the attempt's dispatched receipt IDs.")
            if change.verdict == "pass" or accepted:
                current = fresh_receipts(run, change.observations)
                require(all(dep in current for dep in unit.dependencies)
                        and set(accepted) == {current[dep] for dep in unit.dependencies},
                        "stale_inputs", "Acceptance receipts must be the fresh proofs for every dependency.")
                require(not set(change.input_receipts).intersection(run.superseded_receipts)
                        and inputs_follow(run, change.input_receipts, accepted),
                        "input_lineage_mismatch", "Fresh acceptance proofs must explicitly re-verify the dispatched inputs.")
            refs = bind_evidence(change.evidence_refs)
            run.receipts[change.receipt_id] = Receipt(
                change.receipt_id, change.unit_id, change.attempt_id, attempt.unit_fingerprint,
                change.workspace, change.input_receipts, change.verifier, change.verdict, refs, run.revision + 1,
                accepted, change.reverifies)
            if change.reverifies is None:
                attempt.receipt_id = change.receipt_id
        case PrepareEffect():
            require(not run.paused, "run_paused", "Run is paused.")
            require_stable_paths(run)
            require(change.operation_id not in run.effects, "duplicate_effect", "Operation ID already exists.")
            require(not any(e.kind == change.kind and e.exact_target == change.exact_target
                            and (e.state in ("prepared", "unknown")
                                 or e.state == "confirmed" and e.expected_fingerprint == change.expected_fingerprint)
                            for e in run.effects.values()), "effect_held", "This native effect cannot be repeated without reconciliation.")
            run.effects[change.operation_id] = Effect(
                change.operation_id, change.kind, change.exact_target, change.expected_fingerprint, change.source_refs)
        case ResolveEffect():
            require(change.operation_id in run.effects, "unknown_effect", "Unknown operation ID.")
            effect = run.effects[change.operation_id]
            require(effect.state not in ("confirmed", "not_occurred"), "terminal_effect", "A resolved effect is immutable.")
            effect.evidence_refs = bind_evidence(change.evidence_refs)
            effect.state = change.state
        case Pause() | Adopt():
            if change.observations is not None:
                check_observations(run, change.observations)
            previous = run.owner_nonce
            if isinstance(change, Adopt):
                run.owner_nonce = uuid.uuid4().hex
                run.context = CoordinatorContext(
                    run.context.workspace, run.context.protected_roots, run.context.source_refs,
                    change.conversation_locator, run.context.budget_ref, run.context.decision_trail_ref)
            run.paused = True
            for attempt in run.attempts.values():
                if attempt.held():
                    attempt.state = "unknown"
            for effect in run.effects.values():
                if effect.state == "prepared":
                    effect.state = "unknown"
            run.handoffs.append(Handoff(run.revision + 1, previous, run.owner_nonce,
                                       "adopt" if isinstance(change, Adopt) else "pause",
                                       change.source_refs, change.next_route))
        case Resume(observations):
            check_observations(run, observations)
            require_stable_paths(run)
            require(run.paused, "invalid_transition", "Run is not paused.")
            run.paused = False
        case _:
            raise StateError("invalid_request", "Expected a closed Change variant.")


class RunView(TypedDict):
    run_uuid: str
    owner_nonce: str
    revision: int
    paused: bool
    context: dict
    plan: dict
    plan_history: list
    units: list
    attempts: list
    receipts: list
    effects: list
    handoffs: list
    handoff: dict
    counts: dict
    unsafe_paths: list


def render(run: Run, store: Path, observations: Observations | None = None) -> RunView:
    if observations is not None:
        observations = check_observations(run, observations)
    fresh = fresh_receipts(run, observations)
    drift = unsafe_paths(run)
    workers = {w.attempt_id: w for w in observations.workers} if observations else {}
    attempts = []
    for attempt in run.attempts.values():
        observed = workers.get(attempt.attempt_id)
        attempts.append({**asdict(attempt), "reservation_held": attempt.held(),
                         "output_path_state": path_state(attempt.output_location),
                         "current_observation": asdict(observed) if observed else None,
                         "current_observed_state": observed.state if observed else
                         ("stopped" if attempt.state == "stopped" else "unknown")})
    units = []
    for unit in run.plan.units:
        held = any(a.unit_id == unit.stable_id and a.held() for a in run.attempts.values())
        status = ("held" if held or drift else "verified" if unit.stable_id in fresh else
                  "ready" if not run.paused and all(dep in fresh for dep in unit.dependencies) else "blocked")
        units.append({"stable_id": unit.stable_id, "readiness": status,
                      "fresh_receipt": fresh.get(unit.stable_id)})
    receipt_views = [{**asdict(r), "fresh": fresh.get(r.unit_id) == r.receipt_id,
                      "superseded": r.receipt_id in run.superseded_receipts}
                     for r in sorted(run.receipts.values(), key=lambda r: r.revision)]
    latest_sources = run.handoffs[-1].source_refs if run.handoffs else ()
    handoff_sources = dict.fromkeys((*run.context.source_refs, *latest_sources))
    result = {
        "run_uuid": run.run_uuid, "owner_nonce": run.owner_nonce, "revision": run.revision, "paused": run.paused,
        "context": asdict(run.context), "plan": asdict(run.plan),
        "plan_history": [asdict(p) for p in run.plan_history],
        "units": units, "attempts": attempts, "receipts": receipt_views,
        "effects": [asdict(e) for e in run.effects.values()], "handoffs": [asdict(h) for h in run.handoffs],
        "unsafe_paths": drift,
        "handoff": {
            "run_uuid": run.run_uuid, "revision": run.revision, "store_path": str(store),
            "source_refs": [asdict(r) for r in handoff_sources],
            "workspace_refs": [asdict(observations.workspace if observations else run.context.workspace)],
            "workspace_observed": observations is not None,
            "worker_observations": attempts,
            "unsafe_paths": drift,
            "uncertain_effects": [asdict(e) for e in run.effects.values() if e.state in ("prepared", "unknown")],
            "next_route": run.handoffs[-1].next_route if run.handoffs else "session-pickup",
        },
        "counts": {status: sum(u["readiness"] == status for u in units)
                   for status in ("verified", "ready", "blocked", "held")},
    }
    return decode(encoded(result))


def duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "invalid_request", f"Duplicate JSON field {key}.")
        result[key] = value
    return result


def invalid_constant(value: str) -> None:
    raise StateError("invalid_request", f"Invalid JSON constant {value}.")


def decode(data: str) -> object:
    try:
        return json.loads(data, object_pairs_hook=duplicate_keys, parse_constant=invalid_constant)
    except json.JSONDecodeError as exc:
        raise StateError("invalid_request", f"Invalid JSON: {exc.msg}.") from exc
    except RecursionError as exc:
        raise StateError("invalid_request", "JSON nesting is too deep.") from exc
    except ValueError as exc:
        raise StateError("invalid_request", "JSON scalar exceeds the decoder's supported limits.") from exc


def connect(store: Path, writable: bool = False) -> sqlite3.Connection:
    require(store.is_file(), "store_missing", f"Store does not exist: {store}.")
    db = sqlite3.connect(store.as_uri() + ("?mode=rw" if writable else "?mode=ro"),
                         uri=True, timeout=10, isolation_level=None)
    db.execute("PRAGMA synchronous=FULL")
    if not writable:
        db.execute("PRAGMA query_only=ON")
    return db


def load(db: sqlite3.Connection) -> Run:
    try:
        require(db.execute("PRAGMA quick_check").fetchall() == [("ok",)],
                "store_corrupt", "SQLite integrity check failed.")
        require(db.execute("PRAGMA user_version").fetchone() == (2,),
                "store_corrupt", "Unsupported store schema.")
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        require(tables == [("changes",), ("run",)], "store_corrupt", "Unexpected store tables.")
        require([r[1:3] for r in db.execute("PRAGMA table_info(run)")] == [("id", "INTEGER"), ("state", "TEXT")]
                and [r[1:3] for r in db.execute("PRAGMA table_info(changes)")] ==
                [("change_id", "TEXT"), ("payload", "TEXT"), ("result", "TEXT")],
                "store_corrupt", "Unexpected store columns.")
        rows = db.execute("SELECT state FROM run WHERE id=1").fetchall()
        require(len(rows) == 1 and db.execute("SELECT count(*) FROM run").fetchone() == (1,),
                "store_corrupt", "Store must contain exactly one run.")
        return parse_run(decode(rows[0][0]))
    except StateError as exc:
        raise StateError("store_corrupt", f"Invalid stored accounting: {exc.message}") from exc
    except sqlite3.DatabaseError as exc:
        raise StateError("store_corrupt", f"Invalid SQLite store: {exc}.") from exc


def create(store: Path, plan: Plan, context: CoordinatorContext) -> RunView:
    store = Path(canonical(str(store)))
    # API callers cross the same strict boundary as request-file callers.
    require(type(plan) is Plan and type(context) is CoordinatorContext,
            "invalid_request", "Expected a Plan and CoordinatorContext.")
    plan, context = parse_plan(decode(encoded(asdict(plan)))), parse_context(decode(encoded(asdict(context))))
    require(Path(context.workspace.canonical_path).is_dir(), "workspace_mismatch", "Workspace does not exist.")
    protected_store(store, context, plan)
    require(store.parent.is_dir(), "store_missing", "Create the external artifact directory first.")
    try:
        fd = os.open(store, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise StateError("store_exists", "Store already exists; use view or explicit adoption.") from exc
    os.close(fd)
    run = Run(str(uuid.uuid4()), uuid.uuid4().hex, 0, context, plan)
    result = render(run, store)
    with closing(sqlite3.connect(store, isolation_level=None)) as db, db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE run (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL)")
        db.execute("CREATE TABLE changes (change_id TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT NOT NULL)")
        db.execute("PRAGMA user_version=2")
        db.execute("INSERT INTO run VALUES (1, ?)", (encoded(asdict(run)),))
    return result


def change_payload(change: Change) -> dict:
    names = {ReplacePlan: "replace_plan", ReserveAttempt: "reserve_attempt", RecordWorker: "record_worker",
             AbandonAttempt: "abandon_attempt",
             RecordReceipt: "record_receipt", PrepareEffect: "prepare_effect", ResolveEffect: "resolve_effect",
             Pause: "pause", Adopt: "adopt", Resume: "resume"}
    require(type(change) in names, "invalid_request", "Expected a closed Change variant.")
    result = {"type": names[type(change)], **asdict(change)}
    if isinstance(change, (Pause, Adopt)) and change.observations is None:
        del result["observations"]
    return result


def apply(store: Path, owner: str, expected_revision: int, change_id: str, change: Change) -> RunView:
    store = Path(canonical(str(store)))
    owner, expected_revision, change_id = identifier(owner), number(expected_revision), identifier(change_id)
    change = parse_change(decode(encoded(change_payload(change))))
    payload = encoded({"owner": owner, "expected_revision": expected_revision, "change": change_payload(change)})
    # Reject known corruption without opening a writer that could checkpoint its WAL.
    with closing(connect(store)) as preflight:
        load(preflight)
    with closing(connect(store, writable=True)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        run = load(db)
        protected_store(store, run.context, run.plan)
        previous = db.execute("SELECT payload, result FROM changes WHERE change_id=?", (change_id,)).fetchone()
        if previous is not None:
            require(previous[0] == payload, "change_id_conflict", "Change ID was used with a different request.")
            # Adoption retries recover their minted nonce, but later owners fence every old retry.
            result = decode(previous[1])
            require(type(result) is dict and result.get("owner_nonce") == run.owner_nonce,
                    "owner_conflict", "A later adoption fenced this request.")
            return result
        require(run.owner_nonce == owner, "owner_conflict", "Owner nonce does not match the coordination instance.")
        require(run.revision == expected_revision, "revision_conflict", "Expected revision is not current.")
        mutate(run, change, store)
        run.revision += 1
        observations = getattr(change, "observations", None)
        result = render(run, store, observations)
        db.execute("UPDATE run SET state=? WHERE id=1", (encoded(asdict(run)),))
        db.execute("INSERT INTO changes VALUES (?, ?, ?)", (change_id, payload, encoded(result)))
    return result


def view(store: Path, observations: Observations | None = None) -> RunView:
    store = Path(canonical(str(store)))
    if observations is not None:
        require(type(observations) is Observations, "invalid_request", "Expected Observations.")
        observations = parse_observations(decode(encoded(asdict(observations))))
    with closing(connect(store)) as db, db:
        db.execute("BEGIN")
        run = load(db)
        protected_store(store, run.context, run.plan)
        return render(run, store, observations)


class JSONArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise StateError("invalid_request", message)


def main(argv: list[str] | None = None) -> int:
    try:
        parser = JSONArgumentParser(description=__doc__)
        parser.add_argument("command", choices=("create", "apply", "view"))
        parser.add_argument("--request-file", required=True)
        args = parser.parse_args(argv)
        request = decode(Path(args.request_file).read_text(encoding="utf-8"))
        match args.command:
            case "create":
                d = obj(request, "store plan context")
                result = create(Path(canonical(d["store"])), parse_plan(d["plan"]), parse_context(d["context"]))
            case "apply":
                d = obj(request, "store owner expected_revision change_id change")
                result = apply(Path(canonical(d["store"])), identifier(d["owner"]), number(d["expected_revision"]),
                               identifier(d["change_id"]), parse_change(d["change"]))
            case "view":
                d = obj(request, "store", "observations")
                result = view(Path(canonical(d["store"])),
                              parse_observations(d["observations"]) if d.get("observations") is not None else None)
    except StateError as exc:
        print(encoded({"ok": False, "error": {"code": exc.code, "message": exc.message}}))
        return 1
    except (OSError, UnicodeError, sqlite3.Error) as exc:
        print(encoded({"ok": False, "error": {"code": "storage_error", "message": str(exc)}}))
        return 1
    print(encoded({"ok": True, "run": result}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

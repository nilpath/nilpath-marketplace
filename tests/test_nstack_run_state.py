"""Run accounting through its Python API, subprocess CLI, and real SQLite store."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src/plugins/nstack/skills/nstack-flow/scripts/run_state.py"
SPEC = importlib.util.spec_from_file_location("nstack_run_state", SCRIPT)
state = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = state
SPEC.loader.exec_module(state)


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def source(path: Path | str = "conversation", locator="message-9") -> dict:
    return {"path_or_url": str(path), "exact_locator": locator}


class RunFixture:
    def __init__(self, root: Path):
        self.root = root
        self.work = root / "work"
        self.work.mkdir()
        self.artifacts = root / "accounting"
        self.artifacts.mkdir()
        self.store = self.artifacts / "run.sqlite"
        self.output = self.work / "outputs"
        self.proof = self.artifacts / "proof.txt"
        self.proof.write_text("Observed native worker and verified test output.\n")
        self.workspace = {
            "repo_identity": "local:demo", "canonical_path": str(self.work),
            "branch": "feature", "head": "head-1", "dirty_digest": sha(b"tracked and untracked contents v1"),
        }
        self.context = {
            "workspace": self.workspace, "protected_roots": [str(self.work)],
            "source_refs": [source()],
        }
        self.plan = {
            "plan_ref": source(self.artifacts / "plan.md", "units"),
            "units": [self.unit("a"), self.unit("b", ["a"])],
        }
        self.current = None
        self.serial = 0

    def unit(self, name, dependencies=None):
        return {
            "stable_id": name, "definition_digest": sha(name.encode()),
            "dependencies": dependencies or [], "acceptance": f"Tests for {name} pass.",
            "exclusive_output": str(self.output / name), "source_refs": [source()],
        }

    def obs(self):
        return {"workspace": copy.deepcopy(self.workspace)}

    def evidence(self):
        return [{"path": str(self.proof)}]

    def create(self):
        self.current = state.create(self.store, state.parse_plan(self.plan), state.parse_context(self.context))
        return self.current

    def apply(self, change, *, change_id=None, owner=None, revision=None):
        self.serial += 1
        result = state.apply(
            self.store, owner or self.current["owner_nonce"],
            self.current["revision"] if revision is None else revision,
            change_id or f"change-{self.serial}", state.parse_change(change),
        )
        self.current = result
        return result

    def reserve(self, name="a", attempt=None, inputs=None, output=None):
        return self.apply({
            "type": "reserve_attempt", "attempt_id": attempt or f"{name}-1", "unit_id": name,
            "input_receipts": inputs or [], "brief_ref": source(self.artifacts / "brief.md", "entire brief"),
            "output_location": str(output or self.output / name), "observations": self.obs(),
        })

    def worker(self, attempt="a-1", status="finished", evidence=None, handle="native-session-7"):
        return self.apply({
            "type": "record_worker", "observation": {
                "attempt_id": attempt, "state": status, "native_handle": handle,
                "evidence_refs": self.evidence() if evidence is None else evidence,
            },
        })

    def receipt_change(self, name="a", attempt=None, receipt=None, inputs=None):
        return {
            "type": "record_receipt", "receipt_id": receipt or f"proof-{name}", "unit_id": name,
            "attempt_id": attempt or f"{name}-1", "workspace": copy.deepcopy(self.workspace),
            "input_receipts": inputs or [], "verifier": "outer coordinator",
            "verdict": "pass", "evidence_refs": self.evidence(), "observations": self.obs(),
        }

    def verify(self, name="a", attempt=None, receipt=None, inputs=None):
        return self.apply(self.receipt_change(name, attempt, receipt, inputs))

    def complete(self, name="a", inputs=None):
        self.reserve(name, inputs=inputs)
        self.worker(f"{name}-1")
        return self.verify(name, inputs=inputs)

    def reverify_change(self, name, previous, receipt, *, attempt=None, inputs=None, accepted=None):
        return self.receipt_change(name, attempt=attempt, receipt=receipt, inputs=inputs) | {
            "reverifies": previous, "acceptance_receipts": accepted or [],
        }

    def reverify(self, name, previous, receipt, *, attempt=None, inputs=None, accepted=None):
        return self.apply(self.reverify_change(name, previous, receipt, attempt=attempt, inputs=inputs, accepted=accepted))

    def cli_request(self, command, request, *, env=None):
        self.serial += 1
        path = self.artifacts / f"request-{self.serial}.json"
        path.write_text(json.dumps(request))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), command, "--request-file", str(path)],
            capture_output=True, text=True, env=env,
        )
        return proc.returncode, json.loads(proc.stdout)


@pytest.fixture
def run(tmp_path):
    return RunFixture(tmp_path)


def error(code):
    return ErrorCode(code)


class ErrorCode:
    def __init__(self, code):
        self.code = code

    def __enter__(self):
        self.caught = pytest.raises(state.StateError)
        self.info = self.caught.__enter__()
        return self.info

    def __exit__(self, *args):
        result = self.caught.__exit__(*args)
        assert self.info.value.code == self.code
        return result


def statuses(result):
    return {u["stable_id"]: (u["readiness"], u["fresh_receipt"]) for u in result["units"]}


def test_create_and_read_only_view_with_minted_owner_and_no_authority(run):
    result = run.create()
    assert result["revision"] == 0
    assert len(result["owner_nonce"]) == 32
    assert statuses(result) == {"a": ("ready", None), "b": ("blocked", None)}
    assert result["counts"] == {"verified": 0, "ready": 1, "blocked": 1, "held": 0}
    before = run.store.read_bytes()
    assert state.view(run.store) == result
    assert run.store.read_bytes() == before
    assert result["context"]["source_refs"] == [source() | {"content_digest": None}]
    assert not ({"approved", "capabilities", "permissions", "allowed_actions"} & set(result))
    with sqlite3.connect(run.store) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (2,)
        assert db.execute("SELECT count(*) FROM run").fetchone() == (1,)
    assert run.store.stat().st_mode & 0o777 == 0o600
    with error("store_exists"):
        run.create()


def test_actual_cli_create_apply_view_and_machine_errors(run):
    code, data = run.cli_request("create", {"store": str(run.store), "plan": run.plan, "context": run.context})
    assert code == 0
    owner = data["run"]["owner_nonce"]
    code, data = run.cli_request("apply", {
        "store": str(run.store), "owner": owner, "expected_revision": 0, "change_id": "pause-1",
        "change": {"type": "pause", "source_refs": [source()], "next_route": "session-pickup"},
    })
    assert code == 0
    assert data["run"]["revision"] == 1
    assert data["run"]["paused"] is True
    code, data = run.cli_request("view", {"store": str(run.store)})
    assert code == 0
    assert data["run"]["handoff"]["store_path"] == str(run.store)
    code, data = run.cli_request("view", {"store": str(run.store), "grant": True})
    assert code == 1
    assert data["ok"] is False
    assert data["error"]["code"] == "invalid_request"
    proc = subprocess.run([sys.executable, str(SCRIPT), "apply"], capture_output=True, text=True)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["error"]["code"] == "invalid_request"
    assert os.access(SCRIPT, os.X_OK)
    request_file = run.artifacts / "direct-view.json"
    request_file.write_text(json.dumps({"store": str(run.store)}))
    direct = subprocess.run([str(SCRIPT), "view", "--request-file", str(request_file)],
                            capture_output=True, text=True)
    assert direct.returncode == 0, direct.stderr
    assert json.loads(direct.stdout)["run"]["revision"] == 1


@pytest.mark.parametrize("payload", [
    '{"store":"x","store":"y"}', '{"store":NaN}', '{"store":', '[]',
])
def test_cli_rejects_duplicate_malformed_and_nonfinite_json(run, payload):
    path = run.artifacts / "bad.json"
    path.write_text(payload)
    proc = subprocess.run([sys.executable, str(SCRIPT), "view", "--request-file", str(path)],
                          capture_output=True, text=True)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["error"]["code"] == "invalid_request"
    assert not run.store.exists()


@pytest.mark.parametrize("mutation, code", [
    (lambda p: p["units"].append(copy.deepcopy(p["units"][0])), "invalid_plan"),
    (lambda p: p["units"][0].update(dependencies=["b"]), "invalid_plan"),
    (lambda p: p["units"][0].update(dependencies=["missing"]), "invalid_plan"),
    (lambda p: p["units"][0].update(stable_id="has spaces"), "invalid_request"),
    (lambda p: p["units"][0].update(definition_digest="fake"), "invalid_request"),
    (lambda p: p["units"][0].update(dependencies=["b", "b"]), "invalid_request"),
    (lambda p: p["units"][0].update(approved=True), "invalid_request"),
    (lambda p: p["units"][0].update(acceptance=""), "invalid_request"),
    (lambda p: p["units"][1].update(exclusive_output=p["units"][0]["exclusive_output"]), "output_conflict"),
    (lambda p: p["units"][1].update(exclusive_output=str(Path(p["units"][0]["exclusive_output"]) / "child")),
     "output_conflict"),
])
def test_invalid_plan_has_no_store_artifact(run, mutation, code):
    mutation(run.plan)
    with error(code):
        run.create()
    assert not run.store.exists()


def test_store_directory_is_outside_workspace_outputs_cleanup_and_symlink_roots(run):
    run.store = run.work / "run.sqlite"
    with error("unsafe_store"):
        run.create()
    run.store = run.artifacts / "run.sqlite"
    run.context["protected_roots"].append(str(run.artifacts))
    with error("unsafe_store"):
        run.create()
    run.context["protected_roots"] = [str(run.work)]
    alias = run.root / "alias"
    alias.symlink_to(run.work, target_is_directory=True)
    run.store = alias / "run.sqlite"
    with error("unsafe_store"):
        run.create()
    assert not run.store.exists()


def test_wrong_owner_revision_and_invalid_change_do_not_write(run):
    run.create()
    pause = {"type": "pause", "source_refs": [], "next_route": "session-pickup"}
    with error("owner_conflict"):
        run.apply(pause, owner="not-the-owner")
    with error("revision_conflict"):
        run.apply(pause, revision=1)
    for bad in [
        {"type": "grant", "scope": "all"},
        pause | {"permission": True},
        {"type": "resume", "observations": run.obs() | {"fresh": True}},
    ]:
        with error("invalid_request"):
            run.apply(bad)
    assert state.view(run.store)["revision"] == 0


def test_idempotent_retry_returns_original_result_and_conflicting_id_fails(run):
    original = run.create()
    change = {"type": "pause", "source_refs": [], "next_route": "session-pickup"}
    first = run.apply(change, change_id="once")
    again = run.apply(change, change_id="once", revision=original["revision"])
    assert again == first
    with error("change_id_conflict"):
        run.apply(change | {"next_route": "orchestrate"}, change_id="once", revision=0)
    run.apply({"type": "resume", "observations": run.obs()})
    assert run.apply(change, change_id="once", revision=0) == first
    assert state.view(run.store)["revision"] == 2


def test_adoption_is_actual_handoff_mints_owner_fences_old_retries_and_holds_workers(run):
    run.create()
    reserved = run.reserve()
    run.worker(status="running")
    old_owner = run.current["owner_nonce"]
    prior_revision = run.current["revision"]
    adoption = {"type": "adopt", "source_refs": [source("actual-chat", "pickup")],
                "next_route": "orchestrate", "conversation_locator": "native-chat-10"}
    adopted = run.apply(adoption, change_id="adopt-1")
    assert adopted["owner_nonce"] != old_owner
    assert adopted["paused"] is True
    assert adopted["attempts"][0]["state"] == "unknown"
    assert adopted["attempts"][0]["reservation_held"] is True
    assert adopted["context"]["conversation_locator"] == "native-chat-10"
    assert adopted["handoffs"][-1]["previous_owner"] == old_owner
    assert adopted["handoffs"][-1]["owner_nonce"] == adopted["owner_nonce"]
    assert run.apply(adoption, owner=old_owner, revision=prior_revision, change_id="adopt-1") == adopted
    with error("owner_conflict"):
        run.apply({"type": "pause", "source_refs": [], "next_route": "pickup"}, owner=old_owner)
    with error("owner_conflict"):
        # An earlier accepted request cannot recover control after a later adoption.
        state.apply(run.store, old_owner, 0, "change-1", state.ReserveAttempt(
            "a-1", "a", (), state.parse_source(source(run.artifacts / "brief.md", "entire brief")),
            str(run.output / "a"), state.parse_observations(run.obs())))
    assert reserved["attempts"][0]["state"] == "reserved"


def test_concurrent_subprocess_expected_revision_has_exactly_one_winner(run):
    run.create()
    paths = []
    for change_id in ("fork-1", "fork-2"):
        request = {
            "store": str(run.store), "owner": run.current["owner_nonce"], "expected_revision": 0,
            "change_id": change_id, "change": {"type": "pause", "source_refs": [], "next_route": change_id},
        }
        path = run.artifacts / f"{change_id}.json"
        path.write_text(json.dumps(request))
        paths.append(path)
    processes = [subprocess.Popen([sys.executable, str(SCRIPT), "apply", "--request-file", str(p)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for p in paths]
    results = []
    for process in processes:
        out, err = process.communicate(timeout=30)
        assert err == ""
        results.append((process.returncode, json.loads(out)))
    assert sorted(code for code, _ in results) == [0, 1]
    assert next(data["error"]["code"] for code, data in results if code) == "revision_conflict"
    assert state.view(run.store)["revision"] == 1
    with sqlite3.connect(run.store) as db:
        assert db.execute("SELECT count(*) FROM changes").fetchone() == (1,)


def test_reserve_before_launch_missing_liveness_is_unknown_and_finish_is_not_verification(run):
    run.create()
    reserved = run.reserve()
    assert reserved["attempts"][0]["state"] == "reserved"
    assert reserved["attempts"][0]["current_observed_state"] == "unknown"
    assert reserved["attempts"][0]["reservation_held"] is True
    assert statuses(reserved) == {"a": ("held", None), "b": ("blocked", None)}
    with error("attempt_mismatch"):
        run.verify()
    with error("invalid_evidence"):
        run.worker(status="running", evidence=[])
    running = run.worker(status="running")
    assert running["attempts"][0]["current_observed_state"] == "unknown"
    obs = run.obs() | {"workers": [{
        "attempt_id": "a-1", "state": "running", "evidence_refs": run.evidence(),
        "native_handle": "native-session-7",
    }]}
    observed = state.view(run.store, state.parse_observations(obs))
    assert observed["attempts"][0]["current_observed_state"] == "running"
    assert observed["revision"] == running["revision"]
    finished = run.worker()
    assert statuses(finished)["a"] == ("held", None)
    assert finished["receipts"] == []
    accepted = run.verify()
    assert statuses(accepted) == {"a": ("verified", "proof-a"), "b": ("ready", None)}
    assert accepted["attempts"][0]["reservation_held"] is False


@pytest.mark.parametrize("field, value", [
    ("repo_identity", "wrong-repo"), ("canonical_path", "/different-workspace"), ("branch", "other"),
    ("head", "head-2"), ("dirty_digest", sha(b"changed")),
])
def test_receipt_requires_exact_observed_workspace(run, field, value):
    run.create()
    run.reserve()
    run.worker()
    change = run.receipt_change()
    change["workspace"][field] = value
    with error("workspace_mismatch"):
        run.apply(change)
    assert state.view(run.store)["receipts"] == []


@pytest.mark.parametrize("evidence_kind", ["none", "missing", "empty", "wrong-digest", "url"])
def test_receipt_requires_real_nonempty_local_content_proof(run, evidence_kind):
    run.create()
    run.reserve()
    run.worker()
    change = run.receipt_change()
    if evidence_kind == "none":
        change["evidence_refs"] = []
    elif evidence_kind == "missing":
        change["evidence_refs"] = [{"path": str(run.artifacts / "missing")}]
    elif evidence_kind == "empty":
        empty = run.artifacts / "empty"
        empty.touch()
        change["evidence_refs"] = [{"path": str(empty)}]
    elif evidence_kind == "wrong-digest":
        change["evidence_refs"][0]["content_digest"] = sha(b"wrong")
    else:
        change["evidence_refs"] = [{"path": "https://example.invalid/proof"}]
    with error("invalid_request" if evidence_kind == "url" else "invalid_evidence"):
        run.apply(change)
    assert state.view(run.store)["revision"] == 2
    assert state.view(run.store)["attempts"][0]["reservation_held"] is True


def test_freshness_requires_observations_head_dirty_content_and_evidence_then_invalidates_dependencies(run):
    run.create()
    run.complete()
    run.complete("b", ["proof-a"])
    fresh = state.view(run.store, state.parse_observations(run.obs()))
    assert statuses(fresh) == {"a": ("verified", "proof-a"), "b": ("verified", "proof-b")}
    assert statuses(state.view(run.store)) == {"a": ("ready", None), "b": ("blocked", None)}
    for field, value in (("head", "head-2"), ("dirty_digest", sha(b"same filenames, different contents"))):
        obs = run.obs()
        obs["workspace"][field] = value
        result = state.view(run.store, state.parse_observations(obs))
        assert statuses(result) == {"a": ("ready", None), "b": ("blocked", None)}
        assert [r["fresh"] for r in result["receipts"]] == [False, False]
        assert len(result["receipts"]) == 2
    run.proof.write_text("Changed evidence bytes without changing its path.\n")
    assert statuses(state.view(run.store, state.parse_observations(run.obs()))) == {
        "a": ("ready", None), "b": ("blocked", None),
    }
    run.proof.unlink()
    assert [r["fresh"] for r in state.view(run.store, state.parse_observations(run.obs()))["receipts"]] == [False, False]


def test_dependency_input_and_attempt_mismatches_fail_and_stale_inputs_cannot_dispatch(run):
    run.create()
    with error("stale_inputs"):
        run.reserve("b", inputs=["imaginary-proof"])
    run.complete()
    with error("stale_inputs"):
        run.reserve("b")
    run.reserve("b", inputs=["proof-a"])
    run.worker("b-1")
    change = run.receipt_change("b", inputs=["proof-a"])
    with error("attempt_mismatch"):
        run.apply(change | {"attempt_id": "a-1"})
    with error("stale_inputs"):
        run.apply(change | {"input_receipts": []})
    run.workspace["dirty_digest"] = sha(b"new dirty bytes")
    with error("stale_inputs"):
        run.verify("b", inputs=["proof-a"])
    assert state.view(run.store)["attempts"][-1]["reservation_held"] is True


def test_supersession_invalidates_history_and_downstream_without_erasing_receipts(run):
    run.create()
    run.complete()
    run.complete("b", ["proof-a"])
    new_plan = copy.deepcopy(run.plan)
    new_plan["units"][0]["definition_digest"] = sha(b"a-v2")
    with error("supersession_required"):
        run.apply({"type": "replace_plan", "plan": new_plan, "supersedes": []})
    result = run.apply({"type": "replace_plan", "plan": new_plan, "supersedes": ["a"]})
    assert len(result["plan_history"]) == 1
    assert len(result["receipts"]) == 2
    assert statuses(state.view(run.store, state.parse_observations(run.obs()))) == {
        "a": ("ready", None), "b": ("blocked", None),
    }
    restored = run.apply({"type": "replace_plan", "plan": run.plan, "supersedes": ["a"]})
    assert [r["superseded"] for r in restored["receipts"]] == [True, True]
    assert statuses(state.view(run.store, state.parse_observations(run.obs()))) == {
        "a": ("ready", None), "b": ("blocked", None),
    }
    removed = copy.deepcopy(new_plan)
    removed["units"] = []
    run.apply({"type": "replace_plan", "plan": removed, "supersedes": ["a", "b"]})
    with error("supersession_required"):
        run.apply({"type": "replace_plan", "plan": run.plan, "supersedes": []})


def test_unknown_attempt_keeps_ancestor_reservations_blocks_replacement_and_allows_only_isolated_retry(run):
    run.create()
    run.reserve(output=run.output / "a" / "child")
    run.apply({"type": "adopt", "source_refs": [], "next_route": "orchestrate"})
    run.apply({"type": "resume", "observations": run.obs()})
    for path in (run.output / "a", run.output / "a" / "child", run.output / "a" / "child" / "nested"):
        with error("reservation_held"):
            run.reserve(attempt="a-2", output=path)
    replacement = copy.deepcopy(run.plan)
    replacement["units"][0]["definition_digest"] = sha(b"replacement")
    with error("reservation_held"):
        run.apply({"type": "replace_plan", "plan": replacement, "supersedes": ["a"]})
    isolated = run.reserve(attempt="a-2", output=run.output / "a" / "isolated")
    assert [a["reservation_held"] for a in isolated["attempts"]] == [True, True]
    run.worker("a-1", "stopped")
    run.worker("a-2", "stopped", handle="native-session-8")
    result = run.apply({"type": "replace_plan", "plan": replacement, "supersedes": ["a"]})
    assert result["revision"] == 7


def test_unfinished_downstream_blocks_plan_changes_to_its_inputs(run):
    run.create()
    run.complete()
    run.reserve("b", inputs=["proof-a"])
    replacement = copy.deepcopy(run.plan)
    replacement["units"][0]["definition_digest"] = sha(b"a-v2")
    with error("reservation_held"):
        run.apply({"type": "replace_plan", "plan": replacement, "supersedes": ["a"]})
    assert state.view(run.store)["revision"] == 4


def test_failed_receipt_is_not_verified_and_retry_uses_new_attempt_identity(run):
    run.create()
    run.reserve()
    run.worker()
    result = run.apply(run.receipt_change() | {"verdict": "fail"})
    assert statuses(result) == {"a": ("ready", None), "b": ("blocked", None)}
    with error("duplicate_attempt"):
        run.reserve()
    run.reserve(attempt="a-2")
    run.worker("a-2")
    result = run.verify(attempt="a-2", receipt="proof-a-2")
    assert statuses(result)["a"] == ("verified", "proof-a-2")
    assert [(r["receipt_id"], r["fresh"]) for r in result["receipts"]] == [("proof-a", False), ("proof-a-2", True)]


def test_effects_only_account_native_results_and_unknown_target_cannot_repeat(run):
    run.create()
    effect = {
        "type": "prepare_effect", "operation_id": "push-1", "kind": "push", "exact_target": "origin feature",
        "expected_fingerprint": "native-head-1", "source_refs": [source()],
    }
    prepared = run.apply(effect)
    assert prepared["effects"][0]["state"] == "prepared"
    with error("effect_held"):
        run.apply(effect | {"operation_id": "push-2", "expected_fingerprint": "native-head-2"})
    with error("invalid_evidence"):
        run.apply({"type": "resolve_effect", "operation_id": "push-1", "state": "confirmed", "evidence_refs": []})
    unknown = run.apply({"type": "resolve_effect", "operation_id": "push-1", "state": "unknown",
                         "evidence_refs": run.evidence()})
    assert unknown["effects"][0]["state"] == "unknown"
    with error("effect_held"):
        run.apply(effect | {"operation_id": "push-2"})
    confirmed = run.apply({"type": "resolve_effect", "operation_id": "push-1", "state": "confirmed",
                           "evidence_refs": run.evidence()})
    assert confirmed["effects"][0]["state"] == "confirmed"
    with error("effect_held"):
        run.apply(effect | {"operation_id": "push-2"})
    with error("terminal_effect"):
        run.apply({"type": "resolve_effect", "operation_id": "push-1", "state": "unknown",
                   "evidence_refs": run.evidence()})
    assert run.apply(effect | {"operation_id": "push-2", "expected_fingerprint": "native-head-2"})["revision"] == 4


def test_pause_is_bookkeeping_keeps_dirty_bytes_proof_and_unknown_resources(run):
    run.create()
    dirty = run.work / "dirty.txt"
    dirty.write_bytes(b"uncommitted \x00 exact bytes")
    run.reserve()
    run.apply({"type": "prepare_effect", "operation_id": "remove-1", "kind": "remove",
               "exact_target": str(run.work), "expected_fingerprint": sha(dirty.read_bytes()), "source_refs": []})
    result = run.apply({"type": "pause", "source_refs": [source()], "next_route": "session-pickup"})
    assert result["paused"] is True
    assert result["attempts"][0]["state"] == "unknown"
    assert result["effects"][0]["state"] == "unknown"
    assert result["handoff"]["revision"] == 3
    assert result["handoff"]["uncertain_effects"][0]["operation_id"] == "remove-1"
    assert dirty.read_bytes() == b"uncommitted \x00 exact bytes"
    assert run.proof.read_text() == "Observed native worker and verified test output.\n"
    with error("run_paused"):
        run.reserve(attempt="a-2")
    run.worker(status="stopped")
    assert state.view(run.store)["attempts"][0]["reservation_held"] is False


@pytest.mark.parametrize("fault", ["exception", "crash"])
@pytest.mark.parametrize("operation", ["pause", "adopt", "reverify", "abandon"])
def test_transaction_fault_after_sql_update_never_leaves_partial_state_or_change_id(run, fault, operation):
    run.create()
    if operation == "reverify":
        run.complete()
        change = run.reverify_change("a", "proof-a", "proof-a-new")
    elif operation == "abandon":
        run.reserve()
        run.worker()
        run.proof = run.artifacts / "abandon-evidence.txt"
        run.proof.write_text("Explicitly retire the finished output without deleting its bytes.\n")
        change = {"type": "abandon_attempt", "attempt_id": "a-1", "evidence_refs": run.evidence()}
    else:
        change = {"type": operation, "source_refs": [], "next_route": "session-pickup"}
    before = state.view(run.store)
    revision = run.current["revision"]
    original_owner = run.current["owner_nonce"]
    code = """
import importlib.util, json, os, sqlite3, sys
spec = importlib.util.spec_from_file_location("rs", sys.argv[1])
rs = importlib.util.module_from_spec(spec)
sys.modules["rs"] = rs
spec.loader.exec_module(rs)
native_connect = sqlite3.connect
class FaultConnection(sqlite3.Connection):
    def execute(self, sql, parameters=()):
        if sql.startswith("INSERT INTO changes"):
            if sys.argv[4] == "crash":
                os._exit(79)
            raise sqlite3.OperationalError("injected transaction fault")
        return super().execute(sql, parameters)
def connect(*args, **kwargs):
    return native_connect(*args, **kwargs, factory=FaultConnection)
rs.sqlite3.connect = connect
try:
    change = rs.parse_change(json.loads(sys.argv[5]))
    rs.apply(rs.Path(sys.argv[2]), sys.argv[3], int(sys.argv[6]), "fault-1", change)
except sqlite3.OperationalError:
    sys.exit(78)
"""
    proc = subprocess.run([sys.executable, "-c", code, str(SCRIPT), str(run.store), original_owner, fault,
                           json.dumps(change), str(revision)],
                          capture_output=True, text=True)
    assert proc.returncode == (79 if fault == "crash" else 78), proc.stderr
    after = state.view(run.store)
    assert after == before
    assert after["revision"] == revision
    assert after["owner_nonce"] == original_owner
    assert after["paused"] is False
    assert after["handoffs"] == []
    with sqlite3.connect(run.store) as db:
        assert db.execute("SELECT count(*) FROM changes").fetchone() == (revision,)
    assert run.apply(change, change_id="fault-1")["revision"] == revision + 1


@pytest.mark.parametrize("corruption", ["bytes", "state", "schema"])
def test_corrupt_store_reports_failure_and_preserves_bytes(run, corruption):
    if corruption == "bytes":
        run.store.write_bytes(b"This is not a SQLite database.\x00")
    else:
        run.create()
        with sqlite3.connect(run.store) as db:
            if corruption == "state":
                db.execute("UPDATE run SET state='{}'")
            else:
                db.execute("PRAGMA user_version=99")
    before = run.store.read_bytes()
    for command, request in (
        ("view", {"store": str(run.store)}),
        ("apply", {"store": str(run.store), "owner": "owner", "expected_revision": 0, "change_id": "corrupt",
                   "change": {"type": "pause", "source_refs": [], "next_route": "session-pickup"}}),
    ):
        code, result = run.cli_request(command, request)
        assert code == 1
        assert result["ok"] is False
        assert result["error"]["code"] in ("store_corrupt", "storage_error")
        assert run.store.read_bytes() == before


def test_no_native_commands_workers_deletion_or_output_writes(run):
    bin_dir = run.artifacts / "bin"
    bin_dir.mkdir()
    log = run.artifacts / "native-calls"
    for name in ("git", "gh", "publish_draft.py", "rm", "worker"):
        path = bin_dir / name
        path.write_text(f"#!/bin/sh\nprintf 'called' >> '{log}'\nexit 77\n")
        path.chmod(0o755)
    env = dict(os.environ, PATH=str(bin_dir))
    marker = run.work / "keep.txt"
    marker.write_text("Keep these exact bytes.\n")
    code, data = run.cli_request("create", {"store": str(run.store), "plan": run.plan, "context": run.context}, env=env)
    assert code == 0
    request = {
        "store": str(run.store), "owner": data["run"]["owner_nonce"], "expected_revision": 0, "change_id": "record-only",
        "change": {"type": "prepare_effect", "operation_id": "remove-1", "kind": "remove",
                   "exact_target": str(run.work), "expected_fingerprint": "observed-native-fingerprint", "source_refs": []},
    }
    code, data = run.cli_request("apply", request, env=env)
    assert code == 0
    assert data["run"]["effects"][0]["state"] == "prepared"
    assert marker.read_text() == "Keep these exact bytes.\n"
    assert not log.exists()
    assert not run.output.exists()


def test_only_upstream_evidence_change_invalidates_unchanged_downstream_proof(run):
    run.create()
    run.complete()
    upstream = run.proof
    downstream = run.artifacts / "downstream.txt"
    downstream.write_text("Independent downstream test evidence.\n")
    run.proof = downstream
    run.complete("b", ["proof-a"])
    before = downstream.read_bytes()
    upstream.write_text("Changed upstream test evidence.\n")
    result = state.view(run.store, state.parse_observations(run.obs()))
    assert statuses(result) == {"a": ("ready", None), "b": ("blocked", None)}
    assert downstream.read_bytes() == before
    assert result["receipts"][1]["evidence_refs"][0]["content_digest"] == sha(before)
    assert result["receipts"][1]["fresh"] is False


def test_reservation_conflicts_through_actual_symlink_and_stopped_identity_cannot_restart(run):
    run.create()
    target = run.output / "a" / "target"
    target.mkdir(parents=True)
    alias = run.output / "a" / "alias"
    alias.symlink_to(target, target_is_directory=True)
    run.reserve(output=target)
    with error("reservation_held"):
        run.reserve(attempt="a-2", output=alias / "nested")
    with error("worker_mismatch"):
        run.worker(status="running", handle="wrong-native-identity")
        run.worker(status="finished", handle="another-native-identity")
    stopped = run.worker(status="stopped", handle="wrong-native-identity")
    assert stopped["attempts"][0]["reservation_held"] is False
    with error("terminal_attempt"):
        run.worker(status="running")
    assert run.reserve(attempt="a-2", output=alias)["attempts"][-1]["output_location"] == str(target)


def test_concurrent_identical_subprocess_retries_commit_one_change(run):
    run.create()
    request = {
        "store": str(run.store), "owner": run.current["owner_nonce"], "expected_revision": 0,
        "change_id": "identical", "change": {"type": "adopt", "source_refs": [], "next_route": "session-pickup"},
    }
    path = run.artifacts / "identical.json"
    path.write_text(json.dumps(request))
    processes = [subprocess.Popen([sys.executable, str(SCRIPT), "apply", "--request-file", str(path)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    results = []
    for process in processes:
        out, err = process.communicate(timeout=30)
        assert process.returncode == 0, err + out
        results.append(json.loads(out))
    assert results[0] == results[1]
    assert results[0]["run"]["owner_nonce"] != request["owner"]
    assert state.view(run.store)["revision"] == 1
    with sqlite3.connect(run.store) as db:
        assert db.execute("SELECT count(*) FROM changes").fetchone() == (1,)


def native_git(work: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
        cwd=work, capture_output=True, text=True, check=True,
    ).stdout.strip()


def observe_native_workspace(run):
    manifest = {str(p.relative_to(run.work)): p.read_bytes().hex() for p in run.work.rglob("*")
                if ".git" not in p.relative_to(run.work).parts and p.is_file()}
    run.workspace.update(
        repo_identity="file:" + native_git(run.work, "rev-parse", "--absolute-git-dir"),
        head=native_git(run.work, "rev-parse", "HEAD"),
        dirty_digest=sha(json.dumps(manifest, sort_keys=True).encode()),
    )


def integration_commit(run, unit):
    body = "VALUE = 'a'\n" if unit == "a" else f"import {chr(ord(unit) - 1)}\nVALUE = {chr(ord(unit) - 1)}.VALUE + '{unit}'\n"
    (run.work / f"{unit}.py").write_text(body)
    native_git(run.work, "add", f"{unit}.py")
    native_git(run.work, "commit", "-m", f"Integrate temporary test unit {unit}")
    (run.work / "dirty.txt").write_text(f"Actual untracked bytes after {unit}.\n")
    observe_native_workspace(run)


def native_proof(run, unit, receipt_id, inputs):
    proc = subprocess.run(
        [sys.executable, "-c", f"import {unit}; assert {unit}.VALUE == {'abc'[:ord(unit)-ord('a')+1]!r}; print('verified {unit}')"],
        cwd=run.work, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    run.proof = run.artifacts / f"{receipt_id}.json"
    run.proof.write_text(json.dumps({
        "attempt_id": f"{unit}-1", "workspace": run.workspace, "dispatched_inputs": inputs,
        "native_command": proc.args, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr,
    }, sort_keys=True))


def test_dependent_code_integration_reverifies_a_b_c_at_actual_new_heads_and_dirty_contents(run):
    native_git(run.work, "init", "--template=", "-b", "feature")
    native_git(run.work, "config", "user.name", "Accounting test")
    native_git(run.work, "config", "user.email", "accounting@example.invalid")
    (run.work / "README.md").write_text("Temporary native integration regression.\n")
    native_git(run.work, "add", "README.md")
    native_git(run.work, "commit", "-m", "Temporary fixture baseline")
    observe_native_workspace(run)
    run.plan["units"].append(run.unit("c", ["b"]))
    run.create()
    baseline_head = run.workspace["head"]
    run.reserve("a")
    integration_commit(run, "a")
    h1, dirty1 = run.workspace["head"], run.workspace["dirty_digest"]
    native_proof(run, "a", "a-h1", [])
    run.worker("a-1")
    run.verify("a", receipt="a-h1")
    run.reserve("b", inputs=["a-h1"])
    integration_commit(run, "b")
    h2, dirty2 = run.workspace["head"], run.workspace["dirty_digest"]
    native_proof(run, "b", "b-h2", ["a-h1"])
    run.worker("b-1")
    with error("stale_inputs"):
        run.verify("b", receipt="b-h2", inputs=["a-h1"])
    native_proof(run, "a", "a-h2", [])
    change = run.reverify_change("a", "a-h1", "a-h2")
    code, result = run.cli_request("apply", {
        "store": str(run.store), "owner": run.current["owner_nonce"],
        "expected_revision": run.current["revision"], "change_id": "a-reverified-h2", "change": change,
    })
    assert code == 0, result
    run.current = result["run"]
    native_proof(run, "b", "b-h2", ["a-h1"])
    run.apply(run.receipt_change("b", receipt="b-h2", inputs=["a-h1"]) | {"acceptance_receipts": ["a-h2"]})
    run.reserve("c", inputs=["b-h2"])
    integration_commit(run, "c")
    h3, dirty3 = run.workspace["head"], run.workspace["dirty_digest"]
    native_proof(run, "c", "c-h3", ["b-h2"])
    run.worker("c-1")
    assert [r["fresh"] for r in state.view(run.store, state.parse_observations(run.obs()))["receipts"]] == [
        False, False, False,
    ]
    old_evidence = {p: p.read_bytes() for p in (run.artifacts / "a-h1.json", run.artifacts / "a-h2.json",
                                              run.artifacts / "b-h2.json")}
    native_proof(run, "a", "a-h3", [])
    run.reverify("a", "a-h2", "a-h3")
    native_proof(run, "b", "b-h3", ["a-h1"])
    run.reverify("b", "b-h2", "b-h3", inputs=["a-h1"], accepted=["a-h3"])
    native_proof(run, "c", "c-h3", ["b-h2"])
    accepted = run.apply(run.receipt_change("c", receipt="c-h3", inputs=["b-h2"]) | {"acceptance_receipts": ["b-h3"]})
    assert len({baseline_head, h1, h2, h3}) == 4
    assert len({dirty1, dirty2, dirty3}) == 3
    assert statuses(accepted) == {"a": ("verified", "a-h3"), "b": ("verified", "b-h3"), "c": ("verified", "c-h3")}
    assert [(a["attempt_id"], a["input_receipts"], a["receipt_id"]) for a in accepted["attempts"]] == [
        ("a-1", [], "a-h1"), ("b-1", ["a-h1"], "b-h2"), ("c-1", ["b-h2"], "c-h3"),
    ]
    receipts = {r["receipt_id"]: r for r in accepted["receipts"]}
    assert receipts["b-h3"]["input_receipts"] == ["a-h1"]
    assert receipts["b-h3"]["acceptance_receipts"] == ["a-h3"]
    assert receipts["b-h3"]["reverifies"] == "b-h2"
    assert receipts["c-h3"]["input_receipts"] == ["b-h2"]
    assert receipts["c-h3"]["acceptance_receipts"] == ["b-h3"]
    assert [r["fresh"] for r in accepted["receipts"]] == [False, False, False, True, True, True]
    assert {r["workspace"]["head"] for r in accepted["receipts"] if r["fresh"]} == {h3}
    assert {r["workspace"]["dirty_digest"] for r in accepted["receipts"] if r["fresh"]} == {dirty3}
    assert all(p.read_bytes() == content for p, content in old_evidence.items())
    unchanged = state.view(run.store)
    assert [r["fresh"] for r in unchanged["receipts"]] == [False] * 6
    (run.work / "dirty.txt").write_text("Unrelated writer changed only dirty bytes.\n")
    observe_native_workspace(run)
    assert run.workspace["head"] == h3
    assert [r["fresh"] for r in state.view(run.store, state.parse_observations(run.obs()))["receipts"]] == [False] * 6
    (run.work / "README.md").write_text("Unrelated writer committed a new head.\n")
    native_git(run.work, "add", "README.md")
    native_git(run.work, "commit", "-m", "Temporary unrelated writer")
    observe_native_workspace(run)
    assert run.workspace["head"] != h3
    assert [r["fresh"] for r in state.view(run.store, state.parse_observations(run.obs()))["receipts"]] == [False] * 6


def test_fresh_replacement_attempt_cannot_substitute_for_dispatched_dependency_lineage(run):
    run.create()
    run.complete()
    run.reserve("b", inputs=["proof-a"])
    run.workspace.update(head="head-2", dirty_digest=sha(b"Integrated B bytes."))
    run.worker("b-1")
    run.reserve("a", attempt="a-replacement")
    run.worker("a-replacement")
    run.verify("a", attempt="a-replacement", receipt="a-other-attempt")
    with error("input_lineage_mismatch"):
        run.apply(run.receipt_change("b", inputs=["proof-a"]) | {"acceptance_receipts": ["a-other-attempt"]})
    with error("stale_inputs"):
        run.apply(run.receipt_change("b", inputs=["a-other-attempt"]) | {"acceptance_receipts": ["a-other-attempt"]})
    with error("reverification_conflict"):
        run.reverify("a", "proof-a", "a-revived")
    current = state.view(run.store)
    attempts = {a["attempt_id"]: a for a in current["attempts"]}
    assert attempts["b-1"]["input_receipts"] == ["proof-a"]
    assert attempts["b-1"]["reservation_held"] is True
    assert attempts["a-1"]["receipt_id"] == "proof-a"


def test_dependency_reverification_invalidates_downstream_until_new_proof_is_recorded(run):
    run.create()
    run.complete()
    run.complete("b", ["proof-a"])
    run.reverify("a", "proof-a", "a-reverified")
    result = state.view(run.store, state.parse_observations(run.obs()))
    assert statuses(result) == {"a": ("verified", "a-reverified"), "b": ("ready", None)}
    with error("stale_inputs"):
        run.reverify("b", "proof-b", "b-reverified", inputs=["proof-a"])
    run.reverify("b", "proof-b", "b-reverified", inputs=["proof-a"], accepted=["a-reverified"])
    assert statuses(state.view(run.store, state.parse_observations(run.obs()))) == {
        "a": ("verified", "a-reverified"), "b": ("verified", "b-reverified"),
    }


@pytest.mark.parametrize("bad, code", [
    ({"reverifies": "missing"}, "unknown_receipt"),
    ({"reverifies": None}, "attempt_mismatch"),
    ({"attempt_id": "b-1"}, "attempt_mismatch"),
    ({"input_receipts": ["proof-b"]}, "stale_inputs"),
    ({"acceptance_receipts": ["proof-b"]}, "stale_inputs"),
    ({"acceptance_receipts": "proof-b"}, "invalid_request"),
    ({"reverifies": 9}, "invalid_request"),
    ({"evidence_refs": []}, "invalid_evidence"),
])
def test_reverification_requires_explicit_identity_lineage_and_evidence(run, bad, code):
    run.create()
    run.complete()
    run.complete("b", ["proof-a"])
    before = state.view(run.store)
    with error(code):
        run.apply(run.reverify_change("a", "proof-a", "a-new") | bad)
    assert state.view(run.store) == before


def test_reverification_never_resurrects_failed_branched_or_superseded_proof(run):
    run.create()
    run.complete()
    run.reverify("a", "proof-a", "a-new")
    with error("reverification_conflict"):
        run.reverify("a", "proof-a", "a-branch")
    failed = run.apply(run.reverify_change("a", "a-new", "a-failed") | {"verdict": "fail"})
    assert statuses(failed)["a"] == ("ready", None)
    with error("reverification_conflict"):
        run.reverify("a", "a-failed", "a-recovered")
    assert statuses(state.view(run.store, state.parse_observations(run.obs())))["a"] == ("ready", None)
    run.reserve(attempt="a-2")
    run.worker("a-2")
    run.verify(attempt="a-2", receipt="a-2-pass")
    plan = copy.deepcopy(run.plan)
    plan["units"][0]["definition_digest"] = sha(b"Changed A definition.")
    run.apply({"type": "replace_plan", "plan": plan, "supersedes": ["a"]})
    with error("attempt_mismatch"):
        run.reverify("a", "a-2-pass", "a-changed", attempt="a-2")
    run.apply({"type": "replace_plan", "plan": run.plan, "supersedes": ["a"]})
    with error("reverification_conflict"):
        run.reverify("a", "a-2-pass", "a-restored", attempt="a-2")


def test_old_evidence_can_remain_stale_while_explicit_new_verification_has_its_own_proof(run):
    run.create()
    run.complete()
    old = state.view(run.store)["receipts"][0]
    run.proof.write_text("Stale old proof bytes changed independently.\n")
    run.proof = run.artifacts / "new-proof.txt"
    run.proof.write_text("Actual new native verification evidence.\n")
    run.workspace.update(head="head-2", dirty_digest=sha(b"new integrated contents"))
    accepted = run.reverify("a", "proof-a", "a-new")
    assert accepted["receipts"][0]["evidence_refs"] == old["evidence_refs"]
    assert accepted["receipts"][0]["workspace"] == old["workspace"]
    assert [r["fresh"] for r in accepted["receipts"]] == [False, True]
    assert accepted["attempts"][0]["receipt_id"] == "proof-a"


@pytest.mark.parametrize("mutation", [
    lambda r: r["receipts"]["a-new"].update(reverifies="a-new"),
    lambda r: r["receipts"]["a-new"].update(reverifies="proof-b"),
    lambda r: r["receipts"]["a-new"].update(input_receipts=["proof-b"]),
    lambda r: r["receipts"]["proof-b"].update(acceptance_receipts=["proof-b"]),
    lambda r: r["attempts"]["a-1"].update(receipt_id="a-new"),
])
def test_corrupt_reverification_lineage_is_rejected_without_repairing_history(run, mutation):
    run.create()
    run.complete()
    run.complete("b", ["proof-a"])
    run.reverify("a", "proof-a", "a-new")
    db = sqlite3.connect(run.store)
    try:
        saved = json.loads(db.execute("SELECT state FROM run").fetchone()[0])
        mutation(saved)
        db.execute("UPDATE run SET state=?", (json.dumps(saved),))
        db.commit()
    finally:
        db.close()
    before = run.store.read_bytes()
    with error("store_corrupt"):
        state.view(run.store)
    assert run.store.read_bytes() == before


@pytest.mark.parametrize("kind", ["push", "reply", "resolve_thread", "rerun", "remove"])
def test_proved_non_occurrence_is_distinct_from_confirmation_and_releases_only_its_effect(run, kind):
    run.create()
    effect = {"type": "prepare_effect", "operation_id": "effect-1", "kind": kind, "exact_target": "native-target",
              "expected_fingerprint": "native-fingerprint", "source_refs": []}
    run.apply(effect)
    with error("invalid_evidence"):
        run.apply({"type": "resolve_effect", "operation_id": "effect-1", "state": "not_occurred", "evidence_refs": []})
    resolved = run.apply({"type": "resolve_effect", "operation_id": "effect-1", "state": "not_occurred",
                          "evidence_refs": run.evidence()})
    assert resolved["effects"][0]["state"] == "not_occurred"
    assert resolved["handoff"]["uncertain_effects"] == []
    run.apply(effect | {"operation_id": "effect-2"})
    run.apply({"type": "resolve_effect", "operation_id": "effect-2", "state": "unknown", "evidence_refs": run.evidence()})
    with error("effect_held"):
        run.apply(effect | {"operation_id": "effect-3"})
    with error("terminal_effect"):
        run.apply({"type": "resolve_effect", "operation_id": "effect-1", "state": "confirmed", "evidence_refs": run.evidence()})


def test_cli_reply_and_thread_resolution_have_independent_accounting_ids(run):
    run.create()
    for operation, kind in (("thread-reply", "reply"), ("thread-resolution", "resolve_thread")):
        code, data = run.cli_request("apply", {
            "store": str(run.store), "owner": run.current["owner_nonce"],
            "expected_revision": run.current["revision"], "change_id": operation,
            "change": {"type": "prepare_effect", "operation_id": operation, "kind": kind,
                       "exact_target": "repo/pr/52/thread/7", "expected_fingerprint": "head-7/thread-fingerprint",
                       "source_refs": []},
        })
        assert code == 0, data
        run.current = data["run"]
    assert [(e["operation_id"], e["kind"], e["state"]) for e in state.view(run.store)["effects"]] == [
        ("thread-reply", "reply", "prepared"), ("thread-resolution", "resolve_thread", "prepared"),
    ]


@pytest.mark.parametrize("pause_type", ["none", "pause", "adopt"])
def test_finished_fact_cannot_regress_through_unknown_or_recovery(run, pause_type):
    run.create()
    run.reserve()
    finished = run.worker()
    original_proof = finished["attempts"][0]["finished_evidence_refs"]
    if pause_type == "none":
        run.worker(status="unknown", evidence=[])
    else:
        run.apply({"type": pause_type, "source_refs": [], "next_route": "session-pickup"})
    unknown = state.view(run.store)
    assert unknown["attempts"][0]["state"] == "unknown"
    assert unknown["attempts"][0]["finished_observed"] is True
    assert unknown["attempts"][0]["finished_evidence_refs"] == original_proof
    with error("invalid_transition"):
        run.worker(status="running")
    assert state.view(run.store)["attempts"][0]["reservation_held"] is True
    run.worker(status="finished")
    accepted = run.verify()
    assert accepted["attempts"][0]["receipt_id"] == "proof-a"


@pytest.mark.parametrize("alias_kind", ["outside", "loop"])
def test_alias_change_after_reservation_is_held_not_corruption_and_pause_adopt_view_remain_available(run, alias_kind):
    run.create()
    target = run.output / "a"
    target.mkdir(parents=True)
    run.reserve()
    target.rmdir()
    destination = run.work / "other-output"
    destination.mkdir()
    target.symlink_to(destination if alias_kind == "outside" else target, target_is_directory=True)
    before = run.store.read_bytes()
    drifted = state.view(run.store)
    assert run.store.read_bytes() == before
    assert drifted["attempts"][0]["output_location"] == str(target)
    assert drifted["plan"]["units"][0]["exclusive_output"] == str(target)
    expected = "drifted" if alias_kind == "outside" else "unsafe"
    assert drifted["attempts"][0]["output_path_state"] == expected
    assert drifted["attempts"][0]["reservation_held"] is True
    assert drifted["unsafe_paths"] == [{"path": str(target), "state": expected}]
    assert statuses(drifted) == {"a": ("held", None), "b": ("held", None)}
    with error("unsafe_path"):
        run.reserve("b", inputs=["missing"])
    paused = run.apply({"type": "pause", "source_refs": [], "next_route": "session-pickup"})
    adopted = run.apply({"type": "adopt", "source_refs": [], "next_route": "session-pickup"})
    assert adopted["owner_nonce"] != paused["owner_nonce"]
    assert adopted["attempts"][0]["output_location"] == str(target)
    with error("unsafe_path"):
        run.apply({"type": "resume", "observations": run.obs()})
    run.worker(status="stopped")
    replacement = copy.deepcopy(run.plan)
    replacement["units"][0]["exclusive_output"] = str(destination)
    run.apply({"type": "replace_plan", "plan": replacement, "supersedes": ["a"]})
    reconciled = run.apply({"type": "resume", "observations": run.obs()})
    assert reconciled["unsafe_paths"] == []
    assert reconciled["attempts"][0]["output_location"] == str(target)
    assert reconciled["attempts"][0]["output_path_state"] == expected
    assert reconciled["attempts"][0]["reservation_held"] is False


def test_cli_oversized_integer_and_live_symlink_loop_produce_json_errors(run):
    path = run.artifacts / "huge.json"
    path.write_text('{"store":' + "7" * 10000 + "}")
    proc = subprocess.run([sys.executable, str(SCRIPT), "view", "--request-file", str(path)],
                          capture_output=True, text=True)
    assert proc.returncode == 1
    assert proc.stderr == ""
    assert json.loads(proc.stdout)["error"]["code"] == "invalid_request"
    loop = run.artifacts / "loop"
    loop.symlink_to(loop)
    code, result = run.cli_request("view", {"store": str(loop)})
    assert code == 1
    assert result["error"]["code"] == "invalid_request"


def test_previous_store_schema_is_preserved_not_silently_migrated(run):
    run.create()
    db = sqlite3.connect(run.store)
    try:
        db.execute("PRAGMA user_version=1")
        db.commit()
    finally:
        db.close()
    before = run.store.read_bytes()
    with error("store_corrupt"):
        state.view(run.store)
    assert run.store.read_bytes() == before


def test_reverification_fork_has_one_winner_idempotent_result_and_no_silent_branch(run):
    run.create()
    run.complete()
    revision = run.current["revision"]
    paths = []
    changes = []
    for name in ("a-reverified-1", "a-reverified-2"):
        change = run.reverify_change("a", "proof-a", name)
        changes.append(change)
        path = run.artifacts / f"{name}.json"
        path.write_text(json.dumps({
            "store": str(run.store), "owner": run.current["owner_nonce"], "expected_revision": revision,
            "change_id": name, "change": change,
        }))
        paths.append(path)
    processes = [subprocess.Popen([sys.executable, str(SCRIPT), "apply", "--request-file", str(path)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for path in paths]
    results = []
    for process in processes:
        out, err = process.communicate(timeout=30)
        assert err == ""
        results.append((process.returncode, json.loads(out)))
    assert sorted(code for code, _ in results) == [0, 1]
    winner = next(i for i, (code, _) in enumerate(results) if code == 0)
    loser = 1 - winner
    assert results[loser][1]["error"]["code"] == "revision_conflict"
    name = changes[winner]["receipt_id"]
    assert run.apply(changes[winner], change_id=name, revision=revision) == results[winner][1]["run"]
    with error("reverification_conflict"):
        run.apply(changes[loser])
    assert state.view(run.store)["attempts"][0]["receipt_id"] == "proof-a"
    assert len(state.view(run.store)["receipts"]) == 2


def test_unresolved_sibling_prevents_reverification_until_native_stop_is_recorded(run):
    run.create()
    run.complete()
    run.reserve(attempt="a-sibling", output=run.output / "a" / "isolated")
    with error("reservation_held"):
        run.reverify("a", "proof-a", "a-new")
    run.worker("a-sibling", "stopped")
    accepted = run.reverify("a", "proof-a", "a-new")
    assert statuses(accepted)["a"] == ("verified", "a-new")
    assert accepted["attempts"][1]["state"] == "stopped"


def test_evidence_alias_change_keeps_history_and_makes_old_proof_stale(run):
    run.create()
    run.complete()
    original = state.view(run.store)["receipts"][0]["evidence_refs"]
    moved = run.artifacts / "moved-proof.txt"
    run.proof.rename(moved)
    run.proof.symlink_to(moved)
    observed = state.view(run.store, state.parse_observations(run.obs()))
    assert observed["receipts"][0]["evidence_refs"] == original
    assert observed["receipts"][0]["fresh"] is False
    assert statuses(observed)["a"] == ("ready", None)


@pytest.mark.parametrize("harness", ["claude", "copilot", "codex"])
def test_contract_cli_paths_render_without_resolving_against_product_cwd(harness):
    from jinja2 import Environment

    template = (SCRIPT.parent.parent / "references/run-contract.md.j2").read_text()
    result = Environment().from_string(template).render(harness=harness, skill_root="/installed/nstack-flow" if harness == "claude" else ".")
    commands = [line for line in result.splitlines() if line.startswith("python3 ")]
    script_path = "/installed/nstack-flow/scripts/run_state.py" if harness == "claude" else "<nstack-flow skill directory>/scripts/run_state.py"
    assert commands == [
        f'python3 "{script_path}" create --request-file /absolute/create.json',
        f'python3 "{script_path}" apply --request-file /absolute/change.json',
        f'python3 "{script_path}" view --request-file /absolute/view.json',
    ]
    assert 'python3 "./scripts/run_state.py"' not in result
    if harness != "claude":
        assert "without changing the\nproduct working directory" in result
        assert "Resolve the installed `nstack-flow` skill directory to its absolute path." in result


def failed_native_proof(run, receipt_id):
    proc = subprocess.run([sys.executable, "-c", "raise SystemExit('B verification failed at the broken snapshot')"],
                          capture_output=True, text=True)
    assert proc.returncode == 1
    assert "B verification failed" in proc.stderr
    run.proof = run.artifacts / f"{receipt_id}.json"
    run.proof.write_text(json.dumps({
        "attempt_id": "b-1", "workspace": run.workspace,
        "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr,
    }, sort_keys=True))


@pytest.mark.parametrize("verification", ["initial", "reverification"])
def test_failed_downstream_reconciles_at_broken_snapshot_without_claiming_upstream_success(run, verification):
    run.create()
    run.complete()
    if verification == "initial":
        run.reserve("b", inputs=["proof-a"])
    else:
        run.complete("b", ["proof-a"])
    dirty = run.work / "broken-integration.txt"
    dirty.write_bytes(b"Broken downstream integration changed actual dirty contents.\n")
    run.workspace.update(head="head-2", dirty_digest=sha(dirty.read_bytes()))
    failed_native_proof(run, "b-failed-h2")
    if verification == "initial":
        run.worker("b-1")
        change = run.receipt_change("b", receipt="b-failed-h2", inputs=["proof-a"])
    else:
        change = run.reverify_change("b", "proof-b", "b-failed-h2", inputs=["proof-a"])
    with error("stale_inputs"):
        run.apply(change | {"verdict": "pass", "acceptance_receipts": ["proof-a"]})
    code, result = run.cli_request("apply", {
        "store": str(run.store), "owner": run.current["owner_nonce"], "expected_revision": run.current["revision"],
        "change_id": "native-b-failure", "change": change | {"verdict": "fail"},
    })
    assert code == 0, result
    failed = run.current = result["run"]
    receipt = failed["receipts"][-1]
    assert receipt["verdict"] == "fail"
    assert receipt["input_receipts"] == ["proof-a"]
    assert receipt["acceptance_receipts"] == []
    assert receipt["workspace"] == run.workspace
    assert receipt["evidence_refs"][0]["content_digest"] == sha(run.proof.read_bytes())
    assert receipt["fresh"] is False
    attempt = next(a for a in failed["attempts"] if a["attempt_id"] == "b-1")
    assert attempt["input_receipts"] == ["proof-a"]
    assert attempt["receipt_id"] == ("b-failed-h2" if verification == "initial" else "proof-b")
    assert attempt["reservation_held"] is False
    assert statuses(state.view(run.store, state.parse_observations(run.obs()))) == {
        "a": ("ready", None), "b": ("blocked", None),
    }
    with error("reverification_conflict"):
        run.reverify("b", "b-failed-h2", "b-cannot-upgrade", inputs=["proof-a"])
    run.proof = run.artifacts / "fresh-upstream.txt"
    run.proof.write_text("Fresh upstream native verification at H2.\n")
    run.reverify("a", "proof-a", "a-h2")
    run.reserve("b", attempt="b-2", inputs=["a-h2"])
    retry = subprocess.run([sys.executable, "-c", "print('B-2 retry verification passed at H2')"],
                           capture_output=True, text=True)
    assert retry.returncode == 0
    run.proof = run.artifacts / "b-2-native-proof.json"
    run.proof.write_text(json.dumps({
        "attempt_id": "b-2", "workspace": run.workspace, "returncode": retry.returncode,
        "stdout": retry.stdout, "stderr": retry.stderr,
    }))
    run.worker("b-2")
    run.verify("b", attempt="b-2", receipt="b-2-h2", inputs=["a-h2"])
    assert next(a for a in state.view(run.store)["attempts"] if a["attempt_id"] == "b-1")["input_receipts"] == ["proof-a"]


@pytest.mark.parametrize("bad, code", [
    ({"evidence_refs": []}, "invalid_evidence"),
    ({"input_receipts": []}, "stale_inputs"),
    ({"acceptance_receipts": ["proof-a"]}, "stale_inputs"),
])
def test_failure_still_requires_original_lineage_and_real_proof_and_cannot_claim_stale_acceptance(run, bad, code):
    run.create()
    run.complete()
    run.reserve("b", inputs=["proof-a"])
    run.workspace.update(head="head-2", dirty_digest=sha(b"Broken integration."))
    run.worker("b-1")
    before = state.view(run.store)
    change = run.receipt_change("b", inputs=["proof-a"]) | {"verdict": "fail"}
    with error(code):
        run.apply(change | bad)
    assert state.view(run.store) == before


def test_failed_receipt_can_record_explicit_fresh_dependencies_without_erasing_that_history(run):
    run.create()
    run.complete()
    run.reserve("b", inputs=["proof-a"])
    run.worker("b-1")
    failed = run.apply(run.receipt_change("b", inputs=["proof-a"]) | {
        "verdict": "fail", "acceptance_receipts": ["proof-a"],
    })
    assert failed["receipts"][-1]["acceptance_receipts"] == ["proof-a"]
    run.workspace.update(head="head-2", dirty_digest=sha(b"Later unrelated change."))
    observed = state.view(run.store, state.parse_observations(run.obs()))
    assert observed["receipts"][-1]["acceptance_receipts"] == ["proof-a"]
    assert observed["receipts"][-1]["verdict"] == "fail"
    assert observed["receipts"][-1]["fresh"] is False
    assert next(a for a in observed["attempts"] if a["attempt_id"] == "b-1")["reservation_held"] is False


@pytest.mark.parametrize("change_type", ["pause", "adopt"])
def test_cli_handoff_includes_latest_refs_fresh_snapshot_and_bound_worker_evidence(run, change_type):
    run.create()
    run.reserve()
    run.worker(status="running")
    original_context = copy.deepcopy(run.current["context"])
    old_owner = run.current["owner_nonce"]
    run.workspace.update(head="head-2", dirty_digest=sha(b"Actual current dirty snapshot."))
    worker = {
        "attempt_id": "a-1", "state": "running", "native_handle": "native-session-7",
        "evidence_refs": run.evidence(),
    }
    observations = run.obs() | {"workers": [worker]}
    latest = source("latest-recovery", "actual handoff message")
    code, result = run.cli_request("apply", {
        "store": str(run.store), "owner": old_owner, "expected_revision": run.current["revision"],
        "change_id": "recovery-current", "change": {
            "type": change_type, "source_refs": [source(), latest], "next_route": "session-pickup",
            "observations": observations,
        },
    })
    assert code == 0, result
    run.current = result["run"]
    handoff = run.current["handoff"]
    assert handoff["workspace_refs"] == [run.workspace]
    assert handoff["workspace_observed"] is True
    assert handoff["source_refs"] == [source() | {"content_digest": None}, latest | {"content_digest": None}]
    current_worker = handoff["worker_observations"][0]["current_observation"]
    assert current_worker["evidence_refs"] == [{"path": str(run.proof), "content_digest": sha(run.proof.read_bytes())}]
    assert current_worker["state"] == "running"
    assert run.current["attempts"][0]["state"] == "unknown"
    assert run.current["attempts"][0]["reservation_held"] is True
    assert run.current["context"]["workspace"] == original_context["workspace"]
    assert (run.current["owner_nonce"] != old_owner) is (change_type == "adopt")
    before = run.store.read_bytes()
    reobserved = state.view(run.store, state.parse_observations(observations))
    assert reobserved["handoff"]["source_refs"] == handoff["source_refs"]
    assert reobserved["handoff"]["worker_observations"][0]["current_observation"] == current_worker
    assert run.store.read_bytes() == before
    cold = state.view(run.store)
    assert cold["handoff"]["source_refs"] == handoff["source_refs"]
    assert cold["handoff"]["workspace_observed"] is False
    assert cold["handoff"]["workspace_refs"] == [original_context["workspace"]]


def test_export_uses_latest_handoff_refs_and_retains_prior_refs_in_history(run):
    run.create()
    run.apply({"type": "pause", "source_refs": [source("first-pause")], "next_route": "pickup"})
    result = run.apply({"type": "adopt", "source_refs": [source("latest-adoption")], "next_route": "orchestrate"})
    assert [r["path_or_url"] for r in result["handoff"]["source_refs"]] == ["conversation", "latest-adoption"]
    assert [h["source_refs"][0]["path_or_url"] for h in result["handoffs"]] == ["first-pause", "latest-adoption"]
    assert [r["path_or_url"] for r in state.view(run.store)["handoff"]["source_refs"]] == ["conversation", "latest-adoption"]


@pytest.mark.parametrize("terminal", ["finished", "stopped", "finished-then-unknown"])
def test_read_only_and_pause_adopt_observations_reject_running_after_irreversible_progress(run, terminal):
    run.create()
    run.reserve()
    run.worker(status="stopped" if terminal == "stopped" else "finished")
    if terminal == "finished-then-unknown":
        run.worker(status="unknown", evidence=[])
    before = state.view(run.store)
    observations = run.obs() | {"workers": [{
        "attempt_id": "a-1", "state": "running", "native_handle": "native-session-7", "evidence_refs": run.evidence(),
    }]}
    with error("invalid_transition"):
        state.view(run.store, state.parse_observations(observations))
    code, result = run.cli_request("view", {"store": str(run.store), "observations": observations})
    assert code == 1
    assert result["error"]["code"] == "invalid_transition"
    for change_type in ("pause", "adopt"):
        with error("invalid_transition"):
            run.apply({"type": change_type, "source_refs": [source("must-not-save")],
                       "next_route": "pickup", "observations": observations})
        assert state.view(run.store) == before


@pytest.mark.parametrize("worker_state", ["running", "finished", "stopped", "unknown"])
def test_supplied_current_worker_proof_is_bound_in_export_without_reconciling_state(run, worker_state):
    run.create()
    run.reserve()
    before = state.view(run.store)
    observations = run.obs() | {"workers": [{
        "attempt_id": "a-1", "state": worker_state, "evidence_refs": run.evidence(),
    }]}
    result = state.view(run.store, state.parse_observations(observations))
    actual = result["handoff"]["worker_observations"][0]["current_observation"]
    assert actual["evidence_refs"] == [{"path": str(run.proof), "content_digest": sha(run.proof.read_bytes())}]
    assert actual["state"] == worker_state
    assert result["attempts"][0]["state"] == "reserved"
    assert result["attempts"][0]["reservation_held"] is True
    assert state.view(run.store) == before
    observations["workers"][0]["evidence_refs"][0]["content_digest"] = sha(b"wrong proof bytes")
    with error("invalid_evidence"):
        state.view(run.store, state.parse_observations(observations))


@pytest.mark.parametrize("change_type", ["pause", "adopt"])
def test_omitted_and_null_recovery_observations_retry_identically(run, change_type):
    run.create()
    original_owner = run.current["owner_nonce"]
    change = {"type": change_type, "source_refs": [source()], "next_route": "pickup"}
    first = run.apply(change, change_id="recovery-once")
    assert run.apply(change | {"observations": None}, change_id="recovery-once", revision=0, owner=original_owner) == first
    assert state.view(run.store)["revision"] == 1


def test_committed_writer_crash_missing_shm_read_only_view_and_apply_with_private_sidecar_modes(run):
    run.create()
    owner = run.current["owner_nonce"]
    code = """
import importlib.util, os, sqlite3, sys
spec = importlib.util.spec_from_file_location("rs", sys.argv[1])
rs = importlib.util.module_from_spec(spec)
sys.modules["rs"] = rs
spec.loader.exec_module(rs)
native_connect = sqlite3.connect
class ExitAfterCommit(sqlite3.Connection):
    def __exit__(self, kind, value, traceback):
        result = super().__exit__(kind, value, traceback)
        if kind is None:
            os._exit(79)
        return result
def connect(*args, **kwargs):
    return native_connect(*args, **kwargs, factory=ExitAfterCommit)
rs.sqlite3.connect = connect
rs.apply(rs.Path(sys.argv[2]), sys.argv[3], 0, "committed", rs.Pause((), "session-pickup"))
"""
    proc = subprocess.run([sys.executable, "-c", code, str(SCRIPT), str(run.store), owner],
                          capture_output=True, text=True)
    assert proc.returncode == 79, proc.stderr
    wal = Path(str(run.store) + "-wal")
    shm = Path(str(run.store) + "-shm")
    assert [p.stat().st_mode & 0o777 for p in (run.store, wal, shm)] == [0o600, 0o600, 0o600]
    db_bytes, wal_bytes = run.store.read_bytes(), wal.read_bytes()
    shm.unlink()
    code, result = run.cli_request("view", {"store": str(run.store)})
    assert code == 0, result
    assert result["run"]["revision"] == 1
    assert result["run"]["paused"] is True
    assert result["run"]["handoffs"][-1]["revision"] == 1
    assert run.store.read_bytes() == db_bytes
    assert wal.read_bytes() == wal_bytes
    assert shm.stat().st_mode & 0o777 == 0o600
    assert state.view(run.store) == result["run"]
    run.current = result["run"]
    assert run.apply({"type": "resume", "observations": run.obs()})["revision"] == 2
    assert state.view(run.store)["paused"] is False


@pytest.mark.parametrize("recovery", ["none", "unknown", "pause", "adopt"])
def test_process_stop_after_finished_does_not_discard_hold_or_verification_history(run, recovery):
    run.create()
    run.reserve()
    finished = run.worker()
    first_evidence = finished["attempts"][0]["finished_evidence_refs"]
    if recovery == "unknown":
        run.worker(status="unknown", evidence=[])
    elif recovery != "none":
        run.apply({"type": recovery, "source_refs": [], "next_route": "pickup"})
    before = state.view(run.store)
    with error("invalid_transition"):
        run.worker(status="stopped")
    assert state.view(run.store) == before
    physical_stop = run.obs() | {"workers": [{
        "attempt_id": "a-1", "state": "stopped", "native_handle": "native-session-7", "evidence_refs": run.evidence(),
    }]}
    observed = state.view(run.store, state.parse_observations(physical_stop))
    assert observed["attempts"][0]["current_observed_state"] == "stopped"
    assert observed["attempts"][0]["reservation_held"] is True
    assert observed["attempts"][0]["finished_evidence_refs"] == first_evidence
    assert state.view(run.store) == before
    run.worker(status="finished")
    accepted = run.verify()
    assert accepted["attempts"][0]["receipt_id"] == "proof-a"
    assert accepted["attempts"][0]["finished_evidence_refs"] == first_evidence


def test_cli_explicit_abandonment_retires_finished_work_without_deleting_or_resurrecting_it(run):
    run.create()
    run.reserve()
    output = run.output / "a"
    output.mkdir(parents=True)
    artifact = output / "finished.txt"
    artifact.write_bytes(b"Keep finished output bytes and proof.\n")
    finished = run.worker()
    first_evidence = finished["attempts"][0]["finished_evidence_refs"]
    run.proof = run.artifacts / "abandonment.txt"
    run.proof.write_text("Coordinator deliberately retires a-1 finished output after native reconciliation.\n")
    change = {"type": "abandon_attempt", "attempt_id": "a-1", "evidence_refs": run.evidence()}
    revision = run.current["revision"]
    code, result = run.cli_request("apply", {
        "store": str(run.store), "owner": run.current["owner_nonce"], "expected_revision": revision,
        "change_id": "abandon-a-1", "change": change,
    })
    assert code == 0, result
    abandoned = run.current = result["run"]
    attempt = abandoned["attempts"][0]
    assert attempt["state"] == "abandoned"
    assert attempt["reservation_held"] is False
    assert attempt["finished_observed"] is True
    assert attempt["finished_evidence_refs"] == first_evidence
    assert attempt["evidence_refs"] == [{"path": str(run.proof), "content_digest": sha(run.proof.read_bytes())}]
    assert attempt["receipt_id"] is None
    assert abandoned["receipts"] == []
    assert artifact.read_bytes() == b"Keep finished output bytes and proof.\n"
    assert run.apply(change, change_id="abandon-a-1", revision=revision) == abandoned
    for worker_state in ("running", "finished", "stopped", "unknown"):
        with error("terminal_attempt"):
            run.worker(status=worker_state)
    with error("attempt_mismatch"):
        run.verify()
    with error("terminal_attempt"):
        run.apply(change)
    with error("duplicate_attempt"):
        run.reserve()
    reserved = run.reserve(attempt="a-2")
    assert [(a["attempt_id"], a["state"], a["reservation_held"]) for a in reserved["attempts"]] == [
        ("a-1", "abandoned", False), ("a-2", "reserved", True),
    ]
    assert artifact.read_bytes() == b"Keep finished output bytes and proof.\n"


@pytest.mark.parametrize("worker_state", ["reserved", "running", "unknown", "finished-then-unknown"])
def test_abandonment_cannot_release_unresolved_workers_without_confirmed_finished_work(run, worker_state):
    run.create()
    run.reserve()
    if worker_state == "finished-then-unknown":
        run.worker()
        run.worker(status="unknown", evidence=[])
    elif worker_state != "reserved":
        run.worker(status=worker_state)
    before = state.view(run.store)
    with error("attempt_mismatch"):
        run.apply({"type": "abandon_attempt", "attempt_id": "a-1", "evidence_refs": run.evidence()})
    assert state.view(run.store) == before
    assert before["attempts"][0]["reservation_held"] is True


def test_abandonment_requires_proof_and_rejects_unknown_fields(run):
    run.create()
    run.reserve()
    run.worker()
    before = state.view(run.store)
    with error("invalid_evidence"):
        run.apply({"type": "abandon_attempt", "attempt_id": "a-1", "evidence_refs": []})
    with error("invalid_request"):
        run.apply({"type": "abandon_attempt", "attempt_id": "a-1", "evidence_refs": run.evidence(), "permission": True})
    assert state.view(run.store) == before


def test_saved_stopped_record_cannot_override_finished_fact_to_drop_reservation(run):
    run.create()
    run.reserve()
    finished = run.worker()
    first_evidence = finished["attempts"][0]["finished_evidence_refs"]
    db = sqlite3.connect(run.store)
    try:
        saved = json.loads(db.execute("SELECT state FROM run").fetchone()[0])
        saved["attempts"]["a-1"]["state"] = "stopped"
        db.execute("UPDATE run SET state=?", (json.dumps(saved),))
        db.commit()
    finally:
        db.close()
    observed = state.view(run.store)
    assert observed["attempts"][0]["state"] == "stopped"
    assert observed["attempts"][0]["reservation_held"] is True
    assert observed["attempts"][0]["finished_evidence_refs"] == first_evidence
    run.current = observed
    with error("reservation_held"):
        run.reserve(attempt="a-2")
    run.worker(status="finished")
    assert run.verify()["attempts"][0]["receipt_id"] == "proof-a"

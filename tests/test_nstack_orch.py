"""Behavioral tests and frozen upstream oracles for the standalone orch CLI."""

from datetime import datetime
import errno
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src/plugins/nstack/skills/nstack-flow/scripts/orch/orch.py"
FIXTURES = ROOT / "tests/fixtures/nstack-python/orch"
TIMESTAMP = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z"
FILENAME = (r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{3}Z"
            r"-[1-9][0-9]*-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.tsv")
UNIT_HEADER = "id\ttrack\tstate\tbranch\tpr\tsha\tbrief\n"
LEDGER_HEADER = "pr\tsha\tverdict\tevidence\tverifier\tts\n"


@pytest.fixture
def orch(tmp_path):
    copied = tmp_path / "orch.py"
    shutil.copyfile(SCRIPT, copied)
    spec = importlib.util.spec_from_file_location("orch_behavior", copied)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.dont_write_bytecode = old
        sys.modules.pop(spec.name, None)


@pytest.fixture
def store(orch, tmp_path):
    with orch._Store(tmp_path / "store") as value:
        value.init()
        yield value


def run_cli(tmp_path, argv, env=None, *, script=SCRIPT):
    copied = tmp_path / "orch-cli.py"
    shutil.copyfile(script, copied)
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("ORCH_STORE", "ORCH_REPO", "PYTHONPATH")}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.update(env or {})
    result = subprocess.run([sys.executable, "-S", str(copied), *argv], cwd=tmp_path,
                            env=environment, capture_output=True)
    return subprocess.CompletedProcess(result.args, result.returncode,
                                       result.stdout.decode("utf-8"), result.stderr.decode("utf-8"))


@pytest.mark.parametrize("platform", ("win32", "freebsd14"))
def test_unsupported_platform_stops_before_store_mutation_or_pid_probe(orch, tmp_path, monkeypatch, capsys, platform):
    monkeypatch.setattr(orch, "sys", SimpleNamespace(**{**vars(sys), "platform": platform}))

    def forbidden_probe(*args):
        pytest.fail("unsupported platform must never invoke os.kill")

    monkeypatch.setattr(orch.os, "kill", forbidden_probe)
    fresh = tmp_path / "fresh"
    assert orch.main(["--store", str(fresh), "init"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: orch supports Linux and macOS only\n"
    assert not fresh.exists()
    existing = tmp_path / "existing"
    existing.mkdir()
    lock = existing / ".orch.lock"
    lock.write_text("4242\n")
    with orch._Store(existing, force=True) as value:
        with pytest.raises(orch.UserError, match="orch supports Linux and macOS only"):
            value._lock()
        assert value._locked is False
    assert lock.read_text() == "4242\n"


def test_init_idempotent_close_and_existing_files(orch, tmp_path):
    path = tmp_path / "store"
    store = orch._Store(path)
    assert store.init() == {"store": str(path)}
    assert (path / "units.tsv").read_text() == UNIT_HEADER
    assert (path / "ledger.tsv").read_text() == LEDGER_HEADER
    assert (path / ".orch.lock").read_text() == f"{os.getpid()}\n"
    (path / "preferences.md").write_text("1. Preserve me.\n")
    assert store.init() == {"store": str(path)}
    assert sorted(p.name for p in path.iterdir()) == [
        ".orch.lock", "frontier.json", "gates.md", "inbox", "ledger.tsv",
        "preferences.md", "units.tsv",
    ]
    assert (path / "preferences.md").read_text() == "1. Preserve me.\n"
    store.close()
    store.close()
    assert not (path / ".orch.lock").exists()
    with orch._Store(path) as reopened:
        assert reopened.standing_show() == [{"number": 1, "line": "Preserve me."}]
        assert not (path / ".orch.lock").exists()


def test_unit_composition_optional_updates_duplicate_and_not_found(orch, store):
    assert store.unit_add("u1", "build", "briefs/u1.md") == {
        "id": "u1", "track": "build", "state": "pending", "branch": "", "pr": "",
        "sha": "", "brief": "briefs/u1.md",
    }
    assert store.unit_add("=SUM(A1)", "+build") == {
        "id": "'=SUM(A1)", "track": "'+build", "state": "pending", "branch": "",
        "pr": "", "sha": "", "brief": "",
    }
    expected = {"id": "u1", "track": "build", "state": "done", "branch": "nstack/u1",
                "pr": "184530", "sha": "abc123", "brief": "briefs/u1.md"}
    assert store.unit_set("u1", "done", "nstack/u1", 184530, "abc123") == expected
    assert store.unit_get("u1") == expected
    assert store.unit_list("done", "build") == [expected]
    assert store.unit_counts() == {"done": 1, "pending": 1}
    assert store.unit_set("u1", "review") == {**expected, "state": "review"}
    with pytest.raises(orch.UserError, match="unit u1 already exists"):
        store.unit_add("u1", "build")
    with pytest.raises(orch.NotFoundError, match="unit missing not found"):
        store.unit_set("missing", "done")
    assert (store.path / "units.tsv").read_text() == (
        UNIT_HEADER + "u1\tbuild\treview\tnstack/u1\t184530\tabc123\tbriefs/u1.md\n"
        "'=SUM(A1)\t'+build\tpending\t\t\t\t\n"
    )


def test_ledger_replacement_keys_verdicts_and_missing(orch, store):
    with pytest.raises(orch.NotFoundError) as missing:
        store.ledger_check(184530, "abc123")
    assert missing.value.output == {
        "compact": "NOT-VERIFIED",
        "json": {"pr": "184530", "sha": "abc123", "verdict": "NOT-VERIFIED"},
    }
    with pytest.raises(orch.UserError, match="verdict must be"):
        store.ledger_record(1, "sha", "looks-good", "report")
    recorded = store.ledger_record(184530, "abc123", "unit-test-verified", "reports/verify.md", "opus")
    datetime.strptime(recorded["ts"], "%Y-%m-%dT%H:%M:%S.%fZ")
    assert re.fullmatch(TIMESTAMP, recorded["ts"])
    assert {key: value for key, value in recorded.items() if key != "ts"} == {
        "pr": "184530", "sha": "abc123", "verdict": "unit-test-verified",
        "evidence": "reports/verify.md", "verifier": "opus",
    }
    assert store.ledger_check(184530, "abc123") == recorded
    assert store.ledger_summary() == {"unit-test-verified": 1}
    store.ledger_record(184530, "abc123", "live-ui-verified", "reports/live.md")
    assert store.ledger_check(184530, "abc123")["verifier"] == ""
    assert store.ledger_summary() == {"live-ui-verified": 1}
    for index, verdict in enumerate(("unit-test-verified", "type-check-only", "verifier-blocked", "verifier-failed"), 1):
        store.ledger_record(index, "sha", verdict, "evidence")
    assert store.ledger_summary() == {
        "live-ui-verified": 1, "type-check-only": 1, "unit-test-verified": 1,
        "verifier-blocked": 1, "verifier-failed": 1,
    }
    assert len((store.path / "ledger.tsv").read_text().splitlines()) == 6


def test_inbox_push_peek_drain_and_generated_order(store):
    first = store.inbox_push("worker-1", "u1", "done", "reports/u1.md")
    assert re.fullmatch(FILENAME, first["filename"])
    assert first["filename"].startswith(first["pointer"]["ts"].replace(":", "-").replace(".", "-"))
    assert {key: val for key, val in first["pointer"].items() if key != "ts"} == {
        "agent": "worker-1", "unit": "u1", "status": "done", "report": "reports/u1.md",
    }
    second = store.inbox_push("worker-2", "u2", "failed")
    assert second["filename"] != first["filename"]
    assert store.inbox_count() == 2
    expected = [item["pointer"] for item in sorted([first, second], key=lambda item: item["filename"])]
    assert store.inbox_drain(peek=True) == expected
    assert store.inbox_count() == 2
    assert store.inbox_drain() == expected
    assert store.inbox_count() == 0
    assert sorted(path.name for path in store.path.iterdir() if path.name.startswith(".inbox-drain")) == []
    assert store.inbox_push("new", "u3", "done")["pointer"]["unit"] == "u3"
    assert store.inbox_count() == 1


def test_live_dead_unknown_force_lock_and_read_only(orch, store):
    path = store.path
    store.close()
    lock = path / ".orch.lock"
    lock.write_text(f"{os.getpid()}\n")
    with orch._Store(path) as reader:
        assert reader.unit_counts() == {}
        assert lock.read_text() == f"{os.getpid()}\n"
    with orch._Store(path) as blocked:
        with pytest.raises(orch.UserError, match=f"store lock held by pid {os.getpid()}"):
            blocked.unit_add("blocked", "build")
    stolen = []
    with orch._Store(path, force=True, on_lock_stolen=stolen.append) as forced:
        assert forced.unit_add("forced", "build")["id"] == "forced"
    assert stolen == [str(os.getpid())]
    assert not lock.exists()
    exited = subprocess.Popen([sys.executable, "-S", "-c", "pass"])
    exited.wait()
    lock.write_text(f"{exited.pid}\n")
    stale = []
    with orch._Store(path, on_stale_lock=stale.append) as recovered:
        assert recovered.unit_add("recovered", "build")["id"] == "recovered"
    assert stale == [str(exited.pid)]
    for holder in ("", "unknown", "01", "+123", "1.0", "99999999999999999999"):
        lock.write_text(holder)
        with orch._Store(path) as blocked:
            with pytest.raises(orch.UserError, match="store lock held by pid"):
                blocked.unit_add("blocked", "build")
        with orch._Store(path, force=True) as forced:
            assert forced.unit_get("forced")["track"] == "build"
            forced.standing_add("Force is explicit.")
        assert not lock.exists()


def test_release_only_own_lock_and_finally_on_error(orch, store):
    path = store.path
    (path / ".orch.lock").write_text("somebody-else\n")
    store.close()
    assert (path / ".orch.lock").read_text() == "somebody-else\n"
    (path / ".orch.lock").unlink()
    with pytest.raises(orch.UserError, match="track must not be empty"):
        with orch._Store(path) as failing:
            failing.unit_add("u1", "")
    assert not (path / ".orch.lock").exists()
    result = run_cli(path.parent, ["--store", str(path), "unit", "add", "u1", "--track", ""])
    assert (result.returncode, result.stdout, result.stderr) == (1, "", "error: track must not be empty\n")
    assert not (path / ".orch.lock").exists()


@pytest.mark.parametrize("kind", ["stale", "force"])
def test_takeover_losing_exclusive_create_preserves_new_holder(orch, store, monkeypatch, kind):
    path = store.path
    store.close()
    lock = path / ".orch.lock"
    old_holder = "424242" if kind == "stale" else "old-holder"
    lock.write_text(old_holder + "\n")
    original_open = Path.open
    original_kill = orch.os.kill
    attempts = 0
    events = []

    def competing_open(target, mode="r", *args, **kwargs):
        nonlocal attempts
        if target == lock and mode == "x":
            attempts += 1
            if attempts == 2:
                with original_open(target, "x", encoding="utf-8") as other:
                    other.write("424243\n")
        return original_open(target, mode, *args, **kwargs)

    def dead_holder(pid, signal):
        if pid == 424242 and signal == 0:
            raise ProcessLookupError(errno.ESRCH, "fixture dead PID")
        return original_kill(pid, signal)

    monkeypatch.setattr(Path, "open", competing_open)
    monkeypatch.setattr(orch.os, "kill", dead_holder)
    with orch._Store(
        path, force=kind == "force",
        on_stale_lock=lambda holder: events.append(("stale", holder)),
        on_lock_stolen=lambda holder: events.append(("force", holder)),
    ) as contender:
        with pytest.raises(orch.UserError) as error:
            contender.unit_add("blocked", "build")
        assert str(error.value) == "store lock held by pid 424243"
        assert events == [(kind, old_holder)]
        assert attempts == 2
        assert contender._locked is False
        assert lock.read_text() == "424243\n"
    assert contender._locked is False
    assert lock.read_text() == "424243\n"
    assert (path / "units.tsv").read_text() == UNIT_HEADER


def test_cli_lazy_lock_and_live_dead_unknown_diagnostics(orch, store):
    path = store.path
    before = run_cli(path.parent, ["unit", "add", "blocked", "--track", "build", "--store", str(path)])
    assert (before.returncode, before.stdout, before.stderr) == (
        1, "", f"error: store lock held by pid {os.getpid()}\n",
    )
    read = run_cli(path.parent, ["--store", str(path), "unit", "list", "--force"])
    assert (read.returncode, read.stdout, read.stderr) == (0, "(no units)\n", "")
    assert (path / ".orch.lock").read_text() == f"{os.getpid()}\n"
    forced = run_cli(path.parent, ["--store", str(path), "unit", "add", "forced", "--track", "build", "--force"])
    assert (forced.returncode, forced.stdout, forced.stderr) == (
        0, "forced\tbuild\tpending\t\t\t\t\n", f"stealing store lock held by pid {os.getpid()}\n",
    )
    assert not (path / ".orch.lock").exists()
    store.close()
    exited = subprocess.Popen([sys.executable, "-S", "-c", "pass"])
    exited.wait()
    (path / ".orch.lock").write_text(f"{exited.pid}\n")
    stale = run_cli(path.parent, ["--store", str(path), "standing", "add", "Recovered."])
    assert (stale.returncode, stale.stdout, stale.stderr) == (
        0, "1. Recovered.\n", f"replacing stale store lock (pid {exited.pid} is dead)\n",
    )
    (path / ".orch.lock").write_text("")
    unknown = run_cli(path.parent, ["--store", str(path), "standing", "add", "Blocked."])
    assert (unknown.returncode, unknown.stdout, unknown.stderr) == (1, "", "error: store lock held by pid unknown\n")
    forced = run_cli(path.parent, ["--store", str(path), "--force", "standing", "add", "Explicit."])
    assert (forced.returncode, forced.stdout, forced.stderr) == (
        0, "2. Explicit.\n", "stealing store lock held by pid unknown\n",
    )
    assert not (path / ".orch.lock").exists()


def test_gates_standing_status_and_reresolution(store):
    store.unit_add("u1", "build")
    gate = {"kind": "open", "id": "release", "question": "Ship now?", "options": "ship,wait", "defaultAnswer": "wait"}
    assert store.gate_park("release", "Ship now?", "ship,wait", "wait") == gate
    assert store.standing_add("Never force push.") == {"number": 1, "line": "Never force push."}
    first = store.status()
    assert first["changed"] == "first render"
    assert first["summary"] == {"unitStates": {"pending": 1}, "ledgerVerdicts": {},
                                "frontierGeneration": 0, "openGateIds": ["release"]}
    assert "| release | open | Ship now? | ship,wait | wait |  |" in (store.path / "status.md").read_text()
    inode = (store.path / "status.md").stat().st_ino
    assert store.status()["changed"] == "no derived changes"
    assert (store.path / "status.md").stat().st_ino != inode
    assert store.gate_resolve("release", "ship") == {**gate, "kind": "resolved", "answer": "ship"}
    assert store.status()["changed"] == "open gates 1->0"
    assert store.gate_list() == []
    assert store.gate_resolve("release", "wait")["answer"] == "wait"
    assert store.gate_park("release", "Changed?", "yes,no", "no") == {
        "kind": "open", "id": "release", "question": "Changed?", "options": "yes,no", "defaultAnswer": "no",
    }
    assert store.standing_show() == [{"number": 1, "line": "Never force push."}]
    assert (store.path / "gates.md").read_text() == (
        "# Gates\n\n## release\n\n- Status: open\n- Question: Changed?\n- Options: yes,no\n- Default: no\n"
    )


@pytest.mark.parametrize("payload", [
    pytest.param("{", id="malformed-json"),
    pytest.param("[]", id="non-object"),
    pytest.param("{}", id="missing-fields"),
    pytest.param(
        '{"unitStates":{},"ledgerVerdicts":{},"frontierGeneration":"0","openGateIds":[]}',
        id="bad-generation",
    ),
    pytest.param(
        '{"unitStates":{"pending":-1},"ledgerVerdicts":{},"frontierGeneration":0,"openGateIds":[]}',
        id="bad-unit-count",
    ),
    pytest.param(
        '{"unitStates":{},"ledgerVerdicts":{"unit-test-verified":"1"},"frontierGeneration":0,"openGateIds":[]}',
        id="bad-ledger-count",
    ),
    pytest.param(
        '{"unitStates":{},"ledgerVerdicts":{},"frontierGeneration":0,"openGateIds":null}',
        id="bad-gate-list",
    ),
    pytest.param(
        '{"unitStates":{},"ledgerVerdicts":{},"frontierGeneration":0,"openGateIds":[1]}',
        id="non-string-gate-id",
    ),
])
def test_invalid_existing_status_summary_recovers_as_first_render(store, payload):
    store.unit_add("u1", "build")
    store.gate_park("release", "Ship now?", "ship,wait", "wait")
    path = store.path / "status.md"
    path.write_text(f"# Old status\n\n<!-- orch-summary {payload} -->\n")
    report = store.status()
    assert report["changed"] == "first render"
    assert report["summary"] == {
        "unitStates": {"pending": 1}, "ledgerVerdicts": {},
        "frontierGeneration": 0, "openGateIds": ["release"],
    }
    rendered = path.read_text()
    assert rendered.startswith("# Orchestrate status\n")
    assert "| u1 | build | pending |  |  |  |  |" in rendered
    assert rendered.endswith(
        '<!-- orch-summary {"unitStates":{"pending":1},"ledgerVerdicts":{},'
        '"frontierGeneration":0,"openGateIds":["release"]} -->\n'
    )
    assert store.status()["changed"] == "no derived changes"


@pytest.mark.parametrize(("filename", "contents", "method", "message"), [
    ("units.tsv", "wrong\n", "unit_list", "units.tsv has an invalid header"),
    ("units.tsv", UNIT_HEADER + "short\trow\n", "unit_list", "units.tsv has a malformed row"),
    ("ledger.tsv", LEDGER_HEADER + "1\tsha\tinvalid\treport\tme\tnow\n", "ledger_summary", "ledger.tsv has invalid verdict invalid"),
    ("frontier.json", '{"generation":"1"}\n', "frontier_show", "frontier.json has an invalid shape"),
    ("frontier.json", "NaN", "frontier_show", "frontier.json is not valid JSON"),
    ("frontier.json", "[]", "frontier_show", "frontier.json must contain an object"),
    ("frontier.json", '{"generation":1,"prs":[]}', "frontier_show", "frontier.json has an invalid shape"),
    ("frontier.json", '{"generation":true,"prs":[],"lowestUnmerged":null}', "frontier_show", "frontier.json has an invalid shape"),
    ("frontier.json", '{"generation":' + "1" * 5000 + ',"prs":[],"lowestUnmerged":null}',
     "frontier_show", "frontier.json has an invalid shape"),
    ("frontier.json", '{"generation":1,"prs":[{}],"lowestUnmerged":null}', "frontier_show", "frontier.json has an invalid PR row"),
    ("inbox/bad.tsv", "too\tshort\n", "inbox_count", "inbox pointer bad.tsv is malformed"),
    ("inbox/bad.tsv", "a\tb\tc\td\te\n\n", "inbox_count", "inbox pointer bad.tsv is malformed"),
    ("gates.md", "# Wrong\n", "gate_list", "gates.md has an invalid heading"),
    ("gates.md", "# Gates\n\n## id\n\nwrong\n", "gate_list", "gates.md has a malformed gate id"),
    ("gates.md", "# Gates\n\n## id\n\n- Status: resolved\n- Question: Q\n- Options: O\n- Default: D\n", "gate_list", "gates.md has invalid status resolved"),
    ("preferences.md", "2. not first\n", "standing_show", "preferences.md has malformed numbering"),
])
def test_malformed_durable_data(orch, store, filename, contents, method, message):
    (store.path / filename).write_text(contents)
    with pytest.raises(orch.UserError) as error:
        getattr(store, method)()
    assert str(error.value) == message


def test_permissive_stored_fields_and_duplicate_gate_fields(orch, store):
    (store.path / "frontier.json").write_text(
        '{"generation":2,"prs":[{"pr":3,"branches":"b","sha":"","state":"CLOSED","extra":5}],'
        '"lowestUnmerged":-7,"extra":null}'
    )
    assert store.frontier_show() == {
        "generation": 2, "prs": [{"pr": 3, "branches": "b", "sha": "", "state": "CLOSED"}], "lowestUnmerged": -7,
    }
    block = "## id\n\n- Status: open\n- Question: old\n- Question: new\n- Options: \n- Default: d"
    (store.path / "gates.md").write_text("# Gates\n\n" + block + "\n")
    assert store.gate_list() == [{"kind": "open", "id": "id", "question": "new", "options": "", "defaultAnswer": "d"}]
    (store.path / "gates.md").write_text("# Gates\n\n" + block + "\n\n" + block + "\n")
    with pytest.raises(orch.UserError, match="gates.md has duplicate gate ids"):
        store.gate_list()


def test_atomic_replace_failure_preserves_old_file_and_cleans_only_own_temp(orch, store, monkeypatch):
    store.unit_add("u1", "build")
    old = (store.path / "units.tsv").read_bytes()
    unrelated = store.path / ".unrelated.tmp"
    unrelated.write_text("not ours")
    observed = []
    def fail_replace(source, target):
        observed.append((source.parent, target.name, source.read_text()))
        assert (store.path / "units.tsv").read_bytes() == old
        raise OSError("fixture replace failed")
    monkeypatch.setattr(orch.os, "replace", fail_replace)
    with pytest.raises(OSError, match="fixture replace failed"):
        store.unit_set("u1", "done")
    assert observed == [(store.path, "units.tsv", UNIT_HEADER + "u1\tbuild\tdone\t\t\t\t\n")]
    assert (store.path / "units.tsv").read_bytes() == old
    assert sorted(path.name for path in store.path.glob("*.tmp")) == [".unrelated.tmp"]
    assert unrelated.read_text() == "not ours"


def test_exclusive_temp_collision_and_inbox_recreation_failure(orch, store, monkeypatch):
    first = store.inbox_push("agent", "u1", "done")
    original_mkdir = Path.mkdir
    def fail_inbox(path, *args, **kwargs):
        if path == store.path / "inbox":
            raise OSError("fixture mkdir failed")
        return original_mkdir(path, *args, **kwargs)
    with monkeypatch.context() as context:
        context.setattr(Path, "mkdir", fail_inbox)
        with pytest.raises(OSError, match="fixture mkdir failed"):
            store.inbox_drain()
    assert store.inbox_drain(peek=True) == [first["pointer"]]
    assert sorted(path.name for path in store.path.glob(".inbox-drain-*")) == []
    fixed = "00000000-0000-4000-8000-000000000000"
    temporary = store.path / f".units.tsv.{os.getpid()}.{fixed}.tmp"
    temporary.write_text("occupied")
    monkeypatch.setattr(orch.uuid, "uuid4", lambda: fixed)
    with pytest.raises(FileExistsError):
        store.unit_add("u1", "build")
    assert (store.path / "units.tsv").read_text() == UNIT_HEADER
    assert not temporary.exists()
    assert store.inbox_drain() == [first["pointer"]]


def test_utf16_gate_and_approved_count_order_and_same_time_inbox_order(orch, store, monkeypatch):
    labels = ["\ue000", "😀", "ä", "z", "A"]
    for index, label in enumerate(labels):
        store.unit_add(f"u{index}", "build")
        store.unit_set(f"u{index}", label)
        store.gate_park(label, "Question?", "a,b", "b")
    assert list(store.unit_counts().items()) == [("A", 1), ("z", 1), ("ä", 1), ("😀", 1), ("\ue000", 1)]
    report = store.status()
    assert report["summary"]["openGateIds"] == ["A", "z", "ä", "😀", "\ue000"]
    generated = re.search(r"Generated: (.+)\n", (store.path / "status.md").read_text())[1]
    assert re.fullmatch(TIMESTAMP, generated)
    datetime.strptime(generated, "%Y-%m-%dT%H:%M:%S.%fZ")
    assert report["gates"][0]["id"] == "\ue000"
    monkeypatch.setattr(orch, "_now", lambda: "2024-01-02T03:04:05.006Z")
    uuids = iter(["ffffffff-ffff-4fff-bfff-ffffffffffff", "00000000-0000-4000-8000-000000000000",
                  "eeeeeeee-eeee-4eee-beee-eeeeeeeeeeee", "11111111-1111-4111-8111-111111111111"])
    monkeypatch.setattr(orch.uuid, "uuid4", lambda: next(uuids))
    store.inbox_push("first", "u1", "done")
    store.inbox_push("second", "u2", "done")
    assert store.inbox_drain(peek=True) == [
        {"ts": "2024-01-02T03:04:05.006Z", "agent": "second", "unit": "u2", "status": "done", "report": ""},
        {"ts": "2024-01-02T03:04:05.006Z", "agent": "first", "unit": "u1", "status": "done", "report": ""},
    ]


def test_permissions_unknown_lock_not_mistaken_for_dead(orch, store, monkeypatch):
    path = store.path
    store.close()
    (path / ".orch.lock").write_text("123\n")
    def denied(pid, signal):
        raise PermissionError(1, "fixture permission denied")
    monkeypatch.setattr(orch.os, "kill", denied)
    with orch._Store(path) as blocked:
        with pytest.raises(orch.UserError, match="store lock held by pid 123"):
            blocked.unit_add("u1", "build")
    assert (path / ".orch.lock").read_text() == "123\n"
    with orch._Store(path, force=True) as forced:
        assert forced.unit_add("u1", "build")["id"] == "u1"
    assert not (path / ".orch.lock").exists()


def test_inbox_ignores_non_files_and_tsv_symlinks(store):
    pointer = store.inbox_push("agent", "u1", "done")
    (store.path / "inbox" / "ignored.txt").write_text("not a pointer")
    (store.path / "inbox" / "directory.tsv").mkdir()
    (store.path / "inbox" / "symlink.tsv").symlink_to(store.path / "inbox" / pointer["filename"])
    assert store.inbox_drain(peek=True) == [pointer["pointer"]]
    assert store.inbox_count() == 1


def test_closed_and_uninitialized_operations(orch, store, tmp_path):
    store.close()
    for operation in (store.unit_list, store.status, store.init, store.inbox_count, store.frontier_show):
        with pytest.raises(orch.UserError, match="store is closed"):
            operation()
    with orch._Store(tmp_path / "missing") as missing:
        for operation in (missing.unit_list, lambda: missing.unit_add("u", "b"), missing.inbox_count):
            with pytest.raises(orch.UserError, match="store is not initialized"):
                operation()
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize("value", ["0", "01", "+1", "-1", " 1", "1 ", "1.0", "1e2", "0x10", "١", "１", "9007199254740992"])
def test_pr_ascii_safe_decimal_boundary(tmp_path, value):
    for argv in (["ledger", "check", value, "sha"],
                 ["unit", "set", "u", "--state", "done", "--pr", value],
                 ["frontier", "set", "--prs", value]):
        result = run_cli(tmp_path, ["--store", "store", *argv])
        assert result.returncode == 1
        assert result.stdout == ""
        assert "positive integer" in result.stderr
    assert not (tmp_path / "store").exists()


def _git(repo, *args):
    environment = {**os.environ, "GIT_AUTHOR_DATE": "2024-01-02T03:04:05+00:00",
                   "GIT_COMMITTER_DATE": "2024-01-02T03:04:05+00:00",
                   "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    return subprocess.run(["git", "-C", str(repo), *args], env=environment,
                          capture_output=True, text=True, check=True).stdout.strip()


def make_git_stack(directory):
    repo = directory / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.name", "Orch Test")
    _git(repo, "config", "user.email", "orch@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "main.txt").write_text("main\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "main")
    shas = {}
    for index, branch in enumerate(("stack/merged", "stack/closed", "stack/open", "stack/draft")):
        _git(repo, "checkout", "-b", branch)
        (repo / f"stack-{index}.txt").write_text(branch + "\n")
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", branch)
        shas[branch] = _git(repo, "rev-parse", branch)
    _git(repo, "checkout", "stack/open")
    return repo, shas


def forge_rows(forge, records):
    if forge == "gh":
        return [{"number": n, "state": "OPEN" if state == "draft" else state.upper(),
                 "headRefName": head, "baseRefName": base} for n, state, head, base in records]
    return [{"number": n, "status": state, "headRef": head, "baseRef": base}
            for n, state, head, base in records]


def forge_queries(forge):
    fields = "number,state,headRefName,baseRefName" if forge == "gh" else "number,status,headRef,baseRef"
    rows = {
        ("--head", "stack/open"): [(11, "open", "stack/open", "stack/closed")],
        ("--head", "stack/closed"): [(13, "closed", "stack/closed", "stack/merged")],
        ("--head", "stack/merged"): [(10, "merged", "stack/merged", "main")],
        ("--base", "stack/open"): [(14, "draft", "stack/draft", "stack/open"),
                                   (15, "closed", "stack/abandoned", "stack/open")],
        ("--base", "stack/draft"): [],
    }
    return [{"argv": ["pr", "list", filter, branch, "--state", "all", "--json", fields],
             "stdout": json.dumps(forge_rows(forge, records)), "code": 0}
            for (filter, branch), records in rows.items()]


def make_forge(directory, forge, queries):
    bin_path = directory / "bin"
    bin_path.mkdir(exist_ok=True)
    data = directory / f"{forge}-responses.json"
    data.write_text(json.dumps(queries))
    log = directory / "forge-log.jsonl"
    executable = bin_path / forge
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json,os,sys\n"
        f"with open({str(log)!r},'a') as f: f.write(json.dumps({{'argv':sys.argv[1:],'cwd':os.getcwd()}})+'\\n')\n"
        f"rows=json.load(open({str(data)!r}))\n"
        "for row in rows:\n"
        " if row['argv']==sys.argv[1:]:\n"
        "  sys.stdout.write(row['stdout']);sys.stderr.write(row.get('stderr',''));sys.exit(row['code'])\n"
        "sys.stderr.write('unexpected forge argv '+repr(sys.argv[1:]));sys.exit(90)\n"
    )
    executable.chmod(0o755)
    return bin_path, log


@pytest.mark.parametrize("forge", ["gh", "origin"])
def test_frontier_linear_chain_generations_and_pin(orch, store, tmp_path, monkeypatch, forge):
    repo, shas = make_git_stack(tmp_path)
    bin_path, log = make_forge(tmp_path, forge, forge_queries(forge))
    monkeypatch.setenv("PATH", str(bin_path) + os.pathsep + os.environ["PATH"])
    expected = {
        "generation": 1,
        "prs": [{"pr": n, "branches": branch, "sha": shas[branch], "state": state}
                for n, branch, state in ((10, "stack/merged", "MERGED"), (13, "stack/closed", "CLOSED"),
                                          (11, "stack/open", "OPEN"), (14, "stack/draft", "OPEN"))],
        "lowestUnmerged": 11,
    }
    assert store.frontier_set(repo, forge) == expected
    assert store.frontier_set(repo, forge, [10, 13, 11, 14]) == {**expected, "generation": 2}
    assert store.frontier_show() == {**expected, "generation": 2}
    for pins, message in (
            ([10, 11, 12], "frontier pin mismatch: missing from resolved chain: 12; extra in resolved chain: 13,14"),
            ([13, 10, 11, 14], "frontier pin mismatch: order differs: expected 13,10,11,14; resolved 10,13,11,14"),
            ([10, 10], "--prs must not contain duplicates")):
        before = (store.path / "frontier.json").read_bytes()
        with pytest.raises(orch.UserError) as error:
            store.frontier_set(repo, forge, pins)
        assert str(error.value) == message
        assert (store.path / "frontier.json").read_bytes() == before
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert rows == [{"argv": query["argv"], "cwd": str(repo)} for _ in range(4) for query in forge_queries(forge)]
    _git(repo, "checkout", "main")
    assert store.frontier_set(repo, forge) == {"generation": 3, "prs": [], "lowestUnmerged": None}


@pytest.mark.parametrize("forge", ["gh", "origin"])
@pytest.mark.parametrize(("output", "message"), [
    ("this line is not forge output", "output is not valid JSON"),
    ("NaN", "output is not valid JSON"),
    ("{}", "output is not a JSON array"),
    ("[{}]", "output has an invalid PR row"),
    ('[{"number":true}]', "output has an invalid PR row"),
    ("[]", "has no pull request"),
])
def test_frontier_bad_forge_output(orch, store, tmp_path, monkeypatch, forge, output, message):
    repo, _ = make_git_stack(tmp_path)
    queries = forge_queries(forge)
    queries[0]["stdout"] = output
    bin_path, _ = make_forge(tmp_path, forge, queries)
    monkeypatch.setenv("PATH", str(bin_path) + os.pathsep + os.environ["PATH"])
    with pytest.raises(orch.UserError, match=message):
        store.frontier_set(repo, forge)
    assert store.frontier_show() == {"generation": 0, "prs": [], "lowestUnmerged": None}


@pytest.mark.parametrize(("change", "message"), [
    ("ambiguous", "branch stack/open has multiple pull requests (#11, #12); close the stale ones first"),
    ("downloop", "pull request base chain loops at branch stack/open"),
    ("uploop", "pull request base chain loops at branch stack/open"),
    ("fork", "stack is not linear: branches stack/draft, other all target stack/open"),
    ("duplicate", "pull request base chain contains duplicate pull requests"),
])
def test_frontier_rejects_non_linear_chains(orch, store, tmp_path, monkeypatch, change, message):
    repo, _ = make_git_stack(tmp_path)
    queries = forge_queries("gh")
    if change == "ambiguous":
        rows = [(11, "open", "stack/open", "stack/closed"), (12, "open", "stack/open", "main")]
        queries[0]["stdout"] = json.dumps(forge_rows("gh", rows))
    elif change == "downloop":
        queries[0]["stdout"] = json.dumps(forge_rows("gh", [(11, "open", "stack/open", "stack/open")]))
    elif change == "uploop":
        queries[3]["stdout"] = json.dumps(forge_rows("gh", [(14, "open", "stack/open", "stack/open")]))
    elif change == "fork":
        queries[3]["stdout"] = json.dumps(forge_rows("gh", [(14, "draft", "stack/draft", "stack/open"),
                                                          (16, "open", "other", "stack/open")]))
    else:
        queries[3]["stdout"] = json.dumps(forge_rows("gh", [(11, "draft", "stack/draft", "stack/open")]))
    bin_path, _ = make_forge(tmp_path, "gh", queries)
    monkeypatch.setenv("PATH", str(bin_path) + os.pathsep + os.environ["PATH"])
    with pytest.raises(orch.UserError) as error:
        store.frontier_set(repo)
    assert str(error.value) == message
    assert store.frontier_show()["generation"] == 0


def test_frontier_missing_executable_not_nonzero_fallback(orch, store, tmp_path, monkeypatch):
    bin_path = tmp_path / "only"
    bin_path.mkdir()
    log = tmp_path / "git-log"
    git = bin_path / "git"
    git.write_text(f"#!{sys.executable}\nimport sys\n"
                   f"with open({str(log)!r},'a') as f: f.write(repr(sys.argv[1:])+'\\n')\n"
                   "sys.exit(1)\n")
    git.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_path))
    with pytest.raises(orch.UserError, match="git symbolic-ref --short HEAD failed"):
        store.frontier_set(tmp_path)
    assert log.read_text().splitlines() == [
        "['symbolic-ref', '--short', 'refs/remotes/origin/HEAD']",
        "['symbolic-ref', '--short', 'HEAD']",
    ]
    git.unlink()
    with pytest.raises(FileNotFoundError):
        store.frontier_set(tmp_path)
    assert store.frontier_show()["generation"] == 0


def test_frontier_forge_nonzero_and_missing_binary_are_failures(orch, store, tmp_path, monkeypatch):
    repo, _ = make_git_stack(tmp_path)
    queries = forge_queries("gh")
    queries[0].update(code=7, stdout="[]", stderr="fixture forge failure")
    bin_path, _ = make_forge(tmp_path, "gh", queries)
    monkeypatch.setenv("PATH", str(bin_path) + os.pathsep + os.environ["PATH"])
    with pytest.raises(orch.UserError) as error:
        store.frontier_set(repo)
    assert str(error.value) == "gh pr list --head stack/open --state all --json number,state,headRefName,baseRefName failed: fixture forge failure"
    assert store.frontier_show() == {"generation": 0, "prs": [], "lowestUnmerged": None}
    (bin_path / "gh").unlink()
    (bin_path / "git").symlink_to(shutil.which("git"))
    monkeypatch.setenv("PATH", str(bin_path))
    with pytest.raises(FileNotFoundError):
        store.frontier_set(repo)
    assert store.frontier_show() == {"generation": 0, "prs": [], "lowestUnmerged": None}


def test_frontier_trunk_origin_default_and_invalid_sha(orch, store, tmp_path, monkeypatch):
    repo, _ = make_git_stack(tmp_path)
    bin_path, _ = make_forge(tmp_path, "gh", forge_queries("gh"))
    monkeypatch.setenv("PATH", str(bin_path) + os.pathsep + os.environ["PATH"])
    _git(repo, "update-ref", "refs/remotes/origin/custom", "main")
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/custom")
    _git(repo, "checkout", "-b", "custom", "main")
    assert store.frontier_set(repo) == {"generation": 1, "prs": [], "lowestUnmerged": None}
    fake_git = bin_path / "git"
    fake_git.write_text(f"#!{sys.executable}\nimport sys\n"
                        "print('main' if sys.argv[-1]=='refs/remotes/origin/HEAD' else "
                        "'stack/open' if sys.argv[-1]=='HEAD' else 'not-a-sha')\n")
    fake_git.chmod(0o755)
    with pytest.raises(orch.UserError, match="git rev-parse stack/merged returned an invalid SHA"):
        store.frontier_set(repo)
    assert store.frontier_show()["generation"] == 1


def normalize_observation(value):
    if isinstance(value, dict):
        return {key: normalize_observation(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_observation(item) for item in value]
    if not isinstance(value, str):
        return value
    for timestamp in re.findall(TIMESTAMP, value):
        datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    for filename in re.findall(FILENAME, value):
        datetime.strptime(filename[:24], "%Y-%m-%dT%H-%M-%S-%fZ")
        assert int(filename[25:].partition("-")[0]) > 0
    value = re.sub(FILENAME, "<INBOX-TS>-<PID>-<UUID>.tsv", value)
    return re.sub(TIMESTAMP, "<TS>", value)


def snapshot_store(path):
    if not path.exists():
        return []
    return [{"path": item.relative_to(path).as_posix(), "contents": item.read_bytes().decode("utf-8")}
            for item in sorted(path.rglob("*")) if item.is_file()]


def expand_paths(value, directory):
    if isinstance(value, str):
        return (value.replace("{STORE}", str(directory / "store"))
                .replace("{REPO}", str(directory / "repo")).replace("{WORKSPACE}", str(directory)))
    if isinstance(value, dict):
        return {key: expand_paths(item, directory) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_paths(item, directory) for item in value]
    return value


ORACLE = json.loads((FIXTURES / "cli.json").read_text())


@pytest.mark.parametrize("scenario", ORACLE["scenarios"], ids=lambda item: item["name"])
def test_pinned_cli_oracle(tmp_path, scenario):
    scenario = expand_paths(scenario, tmp_path)
    env = {}
    if "forge" in scenario:
        make_git_stack(tmp_path)
        bin_path, log = make_forge(tmp_path, scenario["forge"], scenario["queries"])
        env["PATH"] = str(bin_path) + os.pathsep + os.environ["PATH"]
    for step in scenario["steps"]:
        for name, contents in step.get("write", {}).items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        result = run_cli(tmp_path, step["argv"], {**env, **step.get("env", {})})
        actual = normalize_observation({
            "code": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
            "files": snapshot_store(tmp_path / "store"),
        })
        expected = step["expected"]
        if step.get("presentation") == "help":
            assert actual["code"] == expected["code"] == 0
            assert actual["stderr"] == expected["stderr"] == ""
            assert actual["files"] == expected["files"]
            for text in step["diagnostics"]:
                assert text in actual["stdout"]
        elif step.get("presentation"):
            assert (actual["code"], actual["stdout"], actual["files"]) == (
                expected["code"], expected["stdout"], expected["files"])
            assert bool(actual["stderr"]) == bool(expected["stderr"])
            for text in step.get("diagnostics", []):
                assert text in actual["stderr"]
        elif step.get("json"):
            assert actual["code"] == expected["code"]
            assert actual["stderr"] == expected["stderr"]
            assert actual["files"] == expected["files"]
            assert json.loads(actual["stdout"]) == json.loads(expected["stdout"])
        else:
            assert actual == expected, step["argv"]
        if "forge_calls" in step:
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            assert calls == step["forge_calls"]


def test_no_site_packages_or_js_runtime(tmp_path):
    binary = tmp_path / "bin"
    binary.mkdir()
    result = run_cli(tmp_path, ["--store", "store", "init"], {"PATH": str(binary)})
    assert result.returncode == 0
    result = run_cli(tmp_path, ["unit", "add", "u", "--track", "build", "--json"],
                     {"PATH": str(binary), "ORCH_STORE": str(tmp_path / "store")})
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "id": "u", "track": "build", "state": "pending", "branch": "", "pr": "", "sha": "", "brief": "",
    }
    assert result.stderr == ""

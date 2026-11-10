"""Behavioral ports and pinned upstream oracles for the standalone PR watcher."""

import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/plugins/nstack/skills/nstack-flow/scripts/watch-pr/watch_pr.py"
FIXTURES = ROOT / "tests/fixtures/nstack-python/watcher"
INPUTS = json.loads((FIXTURES / "inputs.json").read_text())
EXPECTED = json.loads((FIXTURES / "expected.json").read_text(), parse_int=float)
TIMERS = json.loads((FIXTURES / "timers.json").read_text())["cases"]
CONTEXT = {"owner": "owner", "repo": "repo", "number": 42}
OPTIONS = {"interval": 10, "sweepInterval": 300, "timeout": 0, "maxQueryErrors": 5, "allowDraft": False}
FACTS = {
    "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "reviewDecision": "APPROVED",
    "headRefOid": "head", "headRefName": "feature", "baseRefName": "main",
    "state": "OPEN", "mergedAt": None, "isDraft": False,
}


@pytest.fixture(scope="module")
def watcher(tmp_path_factory):
    path = tmp_path_factory.mktemp("watcher-copy") / "watch_pr.py"
    shutil.copyfile(SOURCE, path)
    spec = importlib.util.spec_from_file_location("_nstack_watch_pr_test_copy", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old
    yield module
    del sys.modules[spec.name]
    assert not list(path.parent.rglob("__pycache__"))


class FakeClock:
    def __init__(self, timeline=None):
        self.seconds = 0
        self.timeline = [] if timeline is None else timeline

    def now(self):
        return self.seconds

    def observed_at(self):
        dt = datetime(2026, 7, 26, tzinfo=timezone.utc) + timedelta(seconds=self.seconds)
        return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def sleep(self, seconds):
        self.timeline.append({"sleep": seconds})
        self.seconds += seconds


class EventStream(io.StringIO):
    def __init__(self, timeline, pretty=False):
        super().__init__()
        self.timeline = timeline
        self.pretty = pretty
        self.pending = ""

    def write(self, text):
        assert self.pending == "", "each event must flush before another write"
        self.pending = text
        return super().write(text)

    def flush(self):
        assert self.pending, "flush follows a complete event"
        assert self.pending.endswith("\n")
        self.timeline.append({"text": self.pending} if self.pretty else {"event": json.loads(self.pending, parse_int=float)})
        self.pending = ""
        super().flush()


def scripted_run(steps, timeline, clock, stream=None):
    remaining = copy.deepcopy(steps)

    def run(argv):
        if stream is not None:
            assert stream.pending == "", "event was not flushed before the next subprocess"
        assert isinstance(argv, list) and all(isinstance(arg, str) for arg in argv)
        timeline.append({"run": list(argv)})
        assert remaining, f"unexpected argv {argv!r}"
        step = remaining.pop(0)
        clock.seconds += step.get("advance", 0)
        return subprocess.CompletedProcess(argv, step.get("code", 0), step.get("stdout", ""), step.get("stderr", ""))

    return run, remaining


def assert_oracle(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            if expected.get("kind") == "json-parse" and key == "detail":
                # The checkpoint permits language-native JSON exception details only.
                assert actual[key].split(": ", 1)[0] == expected[key].split(": ", 1)[0]
                assert len(actual[key]) > len(actual[key].split(": ", 1)[0]) + 2
            else:
                assert_oracle(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for got, want in zip(actual, expected):
            assert_oracle(got, want)
    else:
        assert actual == expected


@pytest.mark.parametrize(
    "test,expected", zip(INPUTS["runtime"], EXPECTED["runtime"], strict=True),
    ids=[row["name"] for row in INPUTS["runtime"]],
)
def test_pinned_runtime_oracle(watcher, test, expected):
    assert test["name"] == expected["name"]
    timeline = []
    clock = FakeClock(timeline)
    out = EventStream(timeline, test["pretty"])
    err = io.StringIO()
    run, remaining = scripted_run(test["steps"], timeline, clock, out)
    code = watcher.main(test["argv"], run=run, clock=clock, stdout=out, stderr=err)
    assert code == expected["code"]
    assert remaining == []
    assert out.pending == ""
    assert err.getvalue() == expected["stderr"]
    assert_oracle(timeline, expected["timeline"])


FUNCTIONS = {
    "assessGitHubMerge": lambda w, args: w.assess_github_merge(args[0]["mergeStateStatus"], args[0]["headRollupState"]),
    "queryBackoffSeconds": lambda w, args: w.query_backoff_seconds(*args),
    "mapRollupNode": lambda w, args: w.map_rollup_node(*args),
    "parseFastCheck": lambda w, args: w.parse_fast_check(*args),
    "parsePullRequest": lambda w, args: w.parse_pull_request(*args),
    "parseReviewThreadPage": lambda w, args: w.parse_review_thread_page(*args),
    "buildReviewThreads": lambda w, args: w.build_review_threads(*args),
    "orderStack": lambda w, args: w.order_stack(*args),
}


@pytest.mark.parametrize(
    "test,expected", zip(INPUTS["pure"], EXPECTED["pure"], strict=True),
    ids=[row["name"] for row in INPUTS["pure"]],
)
def test_pinned_domain_oracle(watcher, test, expected):
    assert test["name"] == expected["name"]
    if "failure" in expected:
        with pytest.raises(watcher.WatcherQueryError) as caught:
            FUNCTIONS[test["function"]](watcher, test["args"])
        assert caught.value.failure == expected["failure"]
    else:
        assert FUNCTIONS[test["function"]](watcher, test["args"]) == expected["value"]


@pytest.mark.parametrize(
    "argv,expected", zip(INPUTS["parsing"], EXPECTED["parsing"], strict=True),
    ids=[str(row) for row in INPUTS["parsing"]],
)
def test_pinned_commander_inputs(watcher, argv, expected):
    if "options" in expected:
        assert watcher.parse_args(argv) == expected["options"]
    elif expected["code"] == 0:
        with pytest.raises(watcher._Help):
            watcher.parse_args(argv)
    else:
        out, err = io.StringIO(), io.StringIO()
        code = watcher.main(argv, run=lambda argv: pytest.fail(f"unexpected subprocess {argv}"),
                            clock=FakeClock(), stdout=out, stderr=err)
        assert code == 64
        assert out.getvalue() == ""
        assert "error:" in err.getvalue()


def snapshot(watcher, number=42, *, checks="SUCCESS", facts=None, history="omit", nodes=()):
    raw_facts = {**FACTS, **(facts or {})}
    ctx = {**CONTEXT, "number": number}
    responses = [raw_facts]
    if raw_facts["state"] not in ("MERGED", "CLOSED") and raw_facts["mergedAt"] is None:
        responses += [
            {"data": {"repository": {"pullRequest": {"reviewThreads": {
                "nodes": list(nodes), "pageInfo": {"hasNextPage": False, "endCursor": None},
            }}}}},
            [{"name": "ci", "state": checks, "bucket": {"SUCCESS": "pass", "FAILURE": "fail", "PENDING": "pending"}[checks]}],
        ]
        if checks != "PENDING" or history == "include":
            responses.append({"data": {"repository": {"pullRequest": {"commits": {"nodes": [
                {"commit": {"oid": "head", "statusCheckRollup": {"state": checks}}}]}}}}})
    timeline = []
    clock = FakeClock(timeline)
    run, remaining = scripted_run([{"stdout": json.dumps(obj)} for obj in responses], timeline, clock)
    row = watcher.read_snapshot(run, ctx, history)
    assert remaining == []
    return row, timeline


def test_ready_proof_replaces_compile_only_invariants(watcher):
    row, _ = snapshot(watcher)
    ready = watcher.classify_pr(row)
    assert ready["kind"] == "ready"
    assert ready["pr"] == {
        "kind": "ready-pr", "context": CONTEXT,
        "proof": {
            "mergeability": "clear", "threads": [],
            "ci": {
                "source": "gh-pr-checks",
                "all": [{"name": "ci", "description": "", "link": "", "workflow": "", "kind": "passed", "reportedState": "SUCCESS"}],
                "hadPreviousPassingCi": False, "kind": "ci-clean", "failed": [], "pending": [],
                "github": {"kind": "allowed", "basis": "merge-state", "mergeStateStatus": "CLEAN", "headRollupState": "SUCCESS"},
            },
            "gate": {"state": "OPEN", "reviewDecision": "APPROVED", "draft": "not-draft"},
        },
    }
    refusal = watcher.assess_github_merge("BLOCKED", "FAILURE")
    assert refusal == {"kind": "refused", "mergeStateStatus": "BLOCKED", "headRollupState": "FAILURE"}
    row["ci"] = {**row["ci"], "kind": "ci-github-rejected", "github": refusal}
    blocker = watcher.classify_pr(row)
    stamp = watcher.verdict_factory(FakeClock(), "single")
    verdict = watcher._blocker_verdict(stamp, blocker["blocker"])
    assert verdict["kind"] == "BLOCKER"
    assert verdict["exitCode"] == 4
    assert "proof" not in verdict["blocker"]


@pytest.mark.parametrize("kind", ["conflicts", "threads", "ci", "gate", "pending", "ready", "merged"])
def test_single_priority_and_readiness(watcher, kind):
    raw_thread = {"id": "T", "isResolved": False, "comments": {"nodes": []}}
    row, _ = snapshot(
        watcher,
        checks="FAILURE" if kind in ("conflicts", "threads", "ci") else "PENDING" if kind == "pending" else "SUCCESS",
        facts={"mergeable": "CONFLICTING"} if kind == "conflicts" else {"isDraft": True} if kind == "gate"
        else {"state": "MERGED", "mergedAt": "now"} if kind == "merged" else {},
        nodes=[raw_thread] if kind in ("conflicts", "threads") else [],
    )
    decision = watcher.classify_pr(row)
    if kind in ("conflicts", "threads", "ci", "gate"):
        assert decision["kind"] == "blocker"
        assert decision["blocker"]["kind"] == {
            "conflicts": "merge-conflicts", "threads": "review-threads", "ci": "failing-checks", "gate": "merge-gate",
        }[kind]
    else:
        assert decision["kind"] == {"pending": "waiting", "ready": "ready", "merged": "merged"}[kind]


def test_stack_tier_major_and_wait_attribution(watcher):
    failed, _ = snapshot(watcher, 10, checks="FAILURE")
    conflict, _ = snapshot(watcher, 11, facts={"mergeable": "CONFLICTING"})
    assert watcher.select_tier_major_stack_decision([failed, conflict]) == {
        "kind": "blocker", "blocker": {"kind": "merge-conflicts", "pr": conflict["context"], "facts": conflict["facts"]},
    }
    ready, _ = snapshot(watcher, 20)
    pending, _ = snapshot(watcher, 21, checks="PENDING")
    assert watcher.select_tier_major_stack_decision([ready, pending]) == {
        "kind": "waiting", "frontier": {"owner": "owner", "repo": "repo", "number": 21},
        "pending": [{"name": "ci", "description": "", "link": "", "workflow": "", "kind": "pending", "reportedState": "PENDING"}],
    }


def test_draft_wait_then_gate(watcher):
    pending, _ = snapshot(watcher, facts={"isDraft": True}, checks="PENDING")
    settled, _ = snapshot(watcher, facts={"isDraft": True})
    assert watcher.classify_pr(pending)["kind"] == "waiting"
    assert watcher.classify_pr(settled) == {
        "kind": "blocker", "blocker": {"kind": "merge-gate", "pr": CONTEXT, "reason": "draft-pr"},
    }
    assert watcher.classify_pr(settled, allow_draft=True)["pr"]["proof"]["gate"]["draft"] == "draft-allowed"


def test_draft_pending_defers_its_gate_before_changes_requested(watcher):
    row, _ = snapshot(watcher, facts={"isDraft": True, "reviewDecision": "CHANGES_REQUESTED"}, checks="PENDING")
    assert watcher.classify_pr(row)["kind"] == "waiting"
    assert watcher.classify_pr(row, allow_draft=True) == {
        "kind": "blocker", "blocker": {"kind": "merge-gate", "pr": CONTEXT, "reason": "changes-requested"},
    }


@pytest.mark.parametrize("bottom,upstack,expected", [
    ("ci", "threads", "review-threads"), ("gate", "ci", "failing-checks"),
    ("pending", "gate", "merge-gate"), ("threads", "conflict", "merge-conflicts"),
])
def test_stack_tier_priority_across_rows(watcher, bottom, upstack, expected):
    def row(kind, number):
        return snapshot(
            watcher, number, checks="FAILURE" if kind == "ci" else "PENDING" if kind == "pending" else "SUCCESS",
            facts={"mergeable": "CONFLICTING"} if kind == "conflict" else {"isDraft": True} if kind == "gate" else {},
            nodes=[{"id": "T", "isResolved": False, "comments": {"nodes": []}}] if kind == "threads" else [],
        )[0]
    decision = watcher.select_tier_major_stack_decision([row(bottom, 1), row(upstack, 2)])
    assert decision["kind"] == "blocker"
    assert decision["blocker"]["kind"] == expected
    assert decision["blocker"]["pr"]["number"] == 2


def test_explicit_context_has_no_subprocess(watcher):
    result = watcher.resolve_context(lambda argv: pytest.fail(f"unexpected subprocess {argv}"), "explicit", "repo", 42)
    assert result == {"owner": "explicit", "repo": "repo", "number": 42}


def test_queue_sweep_transitions_are_frozen(watcher):
    queue = [{**CONTEXT, "number": number} for number in (20, 21, 22)]
    initial = watcher.create_queue_state(queue, 0)
    first, _ = snapshot(watcher, 20)
    state, rows = watcher.apply_queue_snapshot(initial, first, 0, OPTIONS)
    assert rows is None
    assert [pr["number"] for pr in state.work.remaining] == [21, 22]
    assert [pr["number"] for pr in initial.work.remaining] == [20, 21, 22]
    second, _ = snapshot(watcher, 21)
    state, rows = watcher.apply_queue_snapshot(state, second, 60, OPTIONS)
    assert rows is None
    assert [pr["number"] for pr in state.work.remaining] == [22]
    third, _ = snapshot(watcher, 22)
    state, rows = watcher.apply_queue_snapshot(state, third, 65, OPTIONS)
    assert [row["context"]["number"] for row in rows] == [20, 21, 22]
    assert state.next_sweep_at == 365
    assert state.work is None
    assert watcher.plan_queue(state, 364).work.frontier == queue[0]
    assert [pr["number"] for pr in watcher.plan_queue(state, 365).work.remaining] == [20, 21, 22]


def test_queue_wait_dedupe_and_merge_queue_not_ready(watcher):
    row, _ = snapshot(watcher, 50)
    state = watcher.create_queue_state([row["context"]], 0)
    state, _ = watcher.apply_queue_snapshot(state, row, 0, OPTIONS)
    first = watcher.evaluate_queue(state, 0, OPTIONS)
    assert first["kind"] == "waiting"
    assert first["reason"] == {"kind": "merge-queue", "unmergedCount": 1}
    assert first["emit"] is True
    second = watcher.evaluate_queue(first["state"], 10, OPTIONS)
    assert second["kind"] == "waiting"
    assert second["emit"] is False
    assert watcher.plan_queue(second["state"], 300).work.remaining == (row["context"],)


def test_queue_deadline_after_blocker_advance_and_completion(watcher):
    one, _ = snapshot(watcher, 1)
    two, _ = snapshot(watcher, 2)
    options = {**OPTIONS, "timeout": 1}
    state = watcher.create_queue_state([one["context"], two["context"]], 0)
    state, _ = watcher.apply_queue_snapshot(state, one, 0, options)
    state, _ = watcher.apply_queue_snapshot(state, two, 0, options)
    waiting = watcher.evaluate_queue(state, 0, options)
    state = watcher.plan_queue(waiting["state"], 10)
    merged, _ = snapshot(watcher, 1, facts={"state": "MERGED", "mergedAt": "now"})
    state, _ = watcher.apply_queue_snapshot(state, merged, 10, options)
    advance = watcher.evaluate_queue(state, 10, options)
    assert advance["kind"] == "advance"
    assert advance["merged"]["number"] == 1
    assert advance["frontier"]["number"] == 2
    assert watcher.evaluate_queue(advance["state"], 10, options)["kind"] == "timeout"
    state = watcher.plan_queue(advance["state"], 10)
    merged_two, _ = snapshot(watcher, 2, facts={"state": "MERGED", "mergedAt": None})
    state, _ = watcher.apply_queue_snapshot(state, merged_two, 10, options)
    complete = watcher.evaluate_queue(state, 10, options)
    assert complete["kind"] == "complete"
    assert [row["mergedAt"] for row in complete["merged"]] == ["now", None]


def test_pending_history_query_planning(watcher):
    pending, timeline = snapshot(watcher, checks="PENDING")
    assert pending["ci"]["kind"] == "ci-pending"
    assert [" ".join(step["run"][:3]) for step in timeline] == ["gh pr view", "gh api graphql", "gh pr checks"]
    settled, settled_timeline = snapshot(watcher)
    failed, failed_timeline = snapshot(watcher, checks="FAILURE")
    assert settled["ci"]["kind"] == "ci-clean"
    assert failed["ci"]["kind"] == "ci-failing"
    assert "commits(last: 50)" in settled_timeline[-1]["run"][4]
    assert "commits(last: 50)" in failed_timeline[-1]["run"][4]
    merged, merged_timeline = snapshot(watcher, facts={"state": "MERGED", "mergedAt": "now"})
    assert merged["kind"] == "merged"
    assert len(merged_timeline) == 1
    assert merged_timeline[0]["run"][:4] == ["gh", "pr", "view", "42"]


@pytest.mark.parametrize("executable", ["gh", "git"])
def test_missing_executable_errors_escape_without_retry(watcher, executable):
    calls = []

    def missing(argv):
        calls.append(argv)
        raise FileNotFoundError(2, "No such file or directory", executable)

    argv = ["--owner", "owner", "--repo", "repo", "--pr", "42"] if executable == "gh" else ["--pr", "42"]
    out = io.StringIO()
    clock = FakeClock()
    with pytest.raises(FileNotFoundError) as caught:
        watcher.main(argv, run=missing, clock=clock, stdout=out)
    assert caught.value.filename == executable
    assert calls[0][0] == executable
    assert len(calls) == 1
    assert clock.timeline == []
    assert out.getvalue() == ""


@pytest.mark.parametrize("error", [RuntimeError("unexpected failure"), PermissionError("not permitted")])
def test_unclassified_errors_escape_without_retry(watcher, error):
    timeline = []
    out = io.StringIO()

    def run(argv):
        timeline.append(argv)
        raise error

    clock = FakeClock()
    with pytest.raises(type(error), match=str(error)):
        watcher.main(["--owner", "owner", "--repo", "repo", "--pr", "42"], run=run, clock=clock, stdout=out)
    assert len(timeline) == 1
    assert timeline[0][:4] == ["gh", "pr", "view", "42"]
    assert clock.timeline == []
    assert out.getvalue() == ""


@pytest.mark.parametrize("oracle", TIMERS, ids=[str(row["seconds"]) for row in TIMERS])
def test_real_clock_retains_timer_delay_bounds(watcher, monkeypatch, oracle):
    sleeps = []
    monkeypatch.setattr(watcher.time, "sleep", sleeps.append)
    watcher._RealClock().sleep(oracle["seconds"])
    assert sleeps == [oracle["expectedSleepSeconds"]]


def test_real_subprocess_boundary_preserves_argv_and_signal_code(watcher, monkeypatch):
    seen = []

    def run(argv, **kwargs):
        seen.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, -15, b"stdout\r\n\xff", b"stderr\rsecond\n")

    monkeypatch.setattr(watcher.subprocess, "run", run)
    result = watcher._run(["gh", "pr", "view", "42", "--repo", "o/$();repo"])
    assert result.returncode == -1
    assert result.stdout == "stdout\r\n\ufffd"
    assert result.stderr == "stderr\rsecond\n"
    assert seen == [(["gh", "pr", "view", "42", "--repo", "o/$();repo"], {
        "stdin": subprocess.DEVNULL, "capture_output": True,
    })]


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_strict_json_constants_are_not_numbers(watcher, value):
    with pytest.raises(watcher.WatcherQueryError) as caught:
        watcher._parse_json('{"value":' + value + "}", "input")
    assert caught.value.failure["kind"] == "json-parse"
    assert caught.value.failure["retryable"] is True
    assert caught.value.failure["detail"].startswith("input: ")
    assert watcher._parse_json('{"value":1e2}', "input") == {"value": 100}


def test_help_and_usage_do_not_read(watcher):
    calls = []

    def run(argv):
        calls.append(argv)
        pytest.fail("help or usage unexpectedly invoked a subprocess")

    out, err = io.StringIO(), io.StringIO()
    assert watcher.main(["--help"], run=run, stdout=out, stderr=err) == 0
    assert "JSON (NDJSON while polling)" in out.getvalue()
    assert err.getvalue() == ""
    out, err = io.StringIO(), io.StringIO()
    assert watcher.main(["--interval", "0"], run=run, stdout=out, stderr=err) == 64
    assert out.getvalue() == ""
    assert "error:" in err.getvalue()
    assert calls == []


def test_render_json_exact_null_and_absent_fields(watcher):
    row, _ = snapshot(watcher, facts={"state": "MERGED", "mergedAt": None})
    verdict = {
        "schemaVersion": 1, "sequence": 1, "observedAt": "2026-07-26T00:00:00.000Z",
        "mode": "single", "kind": "STATUS", "terminal": True, "exitCode": 0,
        "reason": "status-only", "rows": [row],
    }
    rendered = watcher.render_json(verdict)
    assert rendered.endswith("\n")
    assert "\n" not in rendered[:-1]
    assert json.loads(rendered) == verdict
    assert "ci" not in json.loads(rendered)["rows"][0]
    assert json.loads(rendered)["rows"][0]["facts"]["mergedAt"] is None
    assert watcher.render_pretty(verdict) == (
        "| PR | CI | Review | Merge |\n| --- | --- | --- | --- |\n"
        "| [#42](https://github.com/owner/repo/pull/42) | \u2014 | \u2014 | ✅ merged |\n"
    )


def test_standalone_no_site_packages_or_js_runtime(tmp_path):
    executable_dir = tmp_path / "bin"
    executable_dir.mkdir()
    gh = executable_dir / "gh"
    gh.write_text(
        "#!" + sys.executable + "\n"
        "import json,sys\n"
        "assert sys.argv[1:4] == ['pr','view','42'], sys.argv\n"
        "print(json.dumps(" + repr({**FACTS, "state": "MERGED", "mergedAt": "now"}) + "))\n"
    )
    gh.chmod(0o755)
    script = tmp_path / "watch_pr.py"
    shutil.copyfile(SOURCE, script)
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", str(script), "--owner", "owner", "--repo", "repo", "--pr", "42"],
        cwd=tmp_path, env={**os.environ, "PATH": str(executable_dir)}, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout)["scope"] == {
        "kind": "single", "pr": {"kind": "merged-pr", "context": CONTEXT, "mergedAt": "now"},
    }
    assert not list(tmp_path.rglob("__pycache__"))


def test_standalone_preserves_cr_and_missing_binary_failure(tmp_path):
    executable_dir = tmp_path / "bin"
    executable_dir.mkdir()
    gh = executable_dir / "gh"
    gh.write_text(
        "#!" + sys.executable + "\n"
        "import sys\nsys.stderr.buffer.write(b'first\\rsecond\\nignored')\nsys.exit(2)\n"
    )
    gh.chmod(0o755)
    script = tmp_path / "watch_pr.py"
    shutil.copyfile(SOURCE, script)
    argv = [sys.executable, "-I", "-S", "-B", str(script), "--owner", "owner", "--repo", "repo",
            "--pr", "42", "--max-query-errors", "1"]
    result = subprocess.run(argv, cwd=tmp_path, env={**os.environ, "PATH": str(executable_dir)},
                            capture_output=True, text=True)
    assert result.returncode == 7
    assert result.stderr == ""
    assert json.loads(result.stdout)["blocker"] == {
        "kind": "status-query", "failures": 1,
        "failure": {"kind": "command-exit", "retryable": True, "code": 2, "detail": "first\rsecond"},
    }
    gh.unlink()
    missing = subprocess.run(argv, cwd=tmp_path, env={**os.environ, "PATH": str(executable_dir)},
                             capture_output=True, text=True)
    assert missing.returncode == 1
    assert missing.stdout == ""
    assert "FileNotFoundError" in missing.stderr
    assert not list(tmp_path.rglob("__pycache__"))

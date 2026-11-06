"""Local tests of fixture evidence capture, not live model compliance."""

import json
import subprocess
from pathlib import Path

import pytest

from behavioral.assertions import assert_observation
from behavioral.runner import FixtureFailure, Observation, ToolCall, _parse_observation, run_skill_observation, run_skill_test


def stream():
    return "\n".join(json.dumps(event) for event in (
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "1", "name": "Read", "input": {"file_path": "source.txt"}},
        ]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "1", "content": "actual source", "is_error": False},
        ]}},
        {"type": "result", "result": "Plan only; implementation is pending.", "is_error": False},
    ))


def test_captures_results_and_artifact_bytes_before_disposal(monkeypatch):
    workspaces = []

    def run(command, *, cwd, **kwargs):
        workspaces.append(Path(cwd))
        (Path(cwd) / "proof.txt").write_bytes(b"observed\n")
        return subprocess.CompletedProcess(command, 0, stream(), "")

    monkeypatch.setattr(subprocess, "run", run)
    result = run_skill_observation("task", None, [], ("proof.txt", "absent.txt"))
    assert [(call.name, call.input) for call in result.calls] == [("Read", {"file_path": "source.txt"})]
    assert [(item.tool_use_id, item.content, item.is_error) for item in result.results] == [("1", "actual source", False)]
    assert result.artifacts == {"proof.txt": b"observed\n", "absent.txt": None}
    assert result.final_output == "Plan only; implementation is pending."
    assert not workspaces[0].exists()
    assert_observation(result, {
        "final_contains": ["implementation is pending"],
        "artifacts": {"proof.txt": "observed\n", "absent.txt": None},
        "forbidden_invocations": [{"type": "Edit"}],
    })
    assert len(run_skill_test("task", None, [])) == 1


@pytest.mark.parametrize("relative", ("../outside", "/tmp/outside"))
def test_capture_refuses_paths_outside_fixture(monkeypatch, relative):
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stream(), ""))
    with pytest.raises(ValueError, match="inside the fixture"):
        run_skill_observation("task", None, [], (relative,))


def test_capture_refuses_symlink_escape(monkeypatch, tmp_path):
    outside = tmp_path / "private"
    outside.write_text("do not capture")

    def run(command, *, cwd, **kwargs):
        (Path(cwd) / "proof").symlink_to(outside)
        return subprocess.CompletedProcess(command, 0, stream(), "")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(ValueError, match="inside the fixture"):
        run_skill_observation("task", None, [], ("proof",))


def test_cli_failure_is_not_a_successful_observation(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "denied"))
    with pytest.raises(RuntimeError, match="denied"):
        run_skill_observation("task", None, [])


def test_cli_without_completion_is_not_a_successful_observation(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""))
    with pytest.raises(RuntimeError, match="without a final result"):
        run_skill_observation("task", None, [])


@pytest.mark.parametrize("returncode, output", [
    (1, '{"type":"result","is_error":true,"result":"native request failed"}'),
    (0, ""),
    (0, '{"malformed private event'),
])
def test_failed_fixtures_keep_selected_bytes_without_dumping_stream(monkeypatch, returncode, output):
    workspaces = []

    def run(command, *, cwd, **kwargs):
        workspaces.append(Path(cwd))
        (Path(cwd) / "proof.txt").write_bytes(b"partial evidence\n")
        return subprocess.CompletedProcess(command, returncode, output, "")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(FixtureFailure) as failure:
        run_skill_observation("task", None, [], ("proof.txt", "absent.txt"))
    assert failure.value.artifacts == {"proof.txt": b"partial evidence\n", "absent.txt": None}
    assert "malformed private event" not in str(failure.value)
    assert not workspaces[0].exists()


def test_timed_out_fixture_preserves_partial_evidence(monkeypatch):
    def run(command, *, cwd, **kwargs):
        (Path(cwd) / "proof.txt").write_bytes(b"partial evidence before timeout\n")
        raise subprocess.TimeoutExpired(command, 900)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(FixtureFailure, match="time budget") as failure:
        run_skill_observation("task", None, [], ("proof.txt",))
    assert failure.value.artifacts == {"proof.txt": b"partial evidence before timeout\n"}


def test_error_result_and_malformed_events_fail_explicitly():
    with pytest.raises(RuntimeError, match="fixture returned an error"):
        _parse_observation('{"type":"result","is_error":true,"result":"budget exhausted"}')
    with pytest.raises(ValueError, match="Malformed"):
        _parse_observation('{"broken')
    with pytest.raises(ValueError, match="final result must be a string"):
        _parse_observation('{"type":"result","result":null}')
    result = _parse_observation('{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"2","content":"failed","is_error":true}]}}')
    assert result.results[0].is_error


def test_artifact_assertions_fail_when_only_prose_claims_success():
    result = Observation([], [], "I wrote proof.txt", {"proof.txt": None})
    with pytest.raises(AssertionError):
        assert_observation(result, {"artifacts": {"proof.txt": "observed"}})


def test_plan_expectations_require_actual_plan_and_no_implementing_worker():
    result = Observation([], [], "Execution pending", {"plan.md": b"Units\nparse -> cli\nExecution pending\n"})
    assert_observation(result, {
        "artifact_contains": {"plan.md": ["Units", "parse -> cli"]},
        "forbidden_roles": ["implementer", "implementer-hard"],
    })
    with pytest.raises(AssertionError):
        assert_observation(Observation([], [], "", {"plan.md": None}), {
            "artifact_contains": {"plan.md": ["Units"]},
        })
    with pytest.raises(AssertionError):
        assert_observation(result, {"artifact_contains": {"plan.md": ["missing dependency"]}})
    for tool in ("Agent", "Task", "task", "spawn_agent"):
        result.calls = [ToolCall(tool, {"prompt": "[nstack role=implementer-hard] change product code"})]
        with pytest.raises(AssertionError):
            assert_observation(result, {"forbidden_roles": ["implementer-hard"]})


@pytest.mark.parametrize("tool, inputs, spec", [
    ("Skill", {"skill": "nstack:nstack-flow"}, {"type": "Skill"}),
    ("Agent", {"subagent_type": "nstack:implementation:nstack-agent"}, {"type": "Agent"}),
    ("Task", {"subagent_type": "nstack:implementation:nstack-agent"}, {"type": "Agent"}),
])
def test_wildcard_forbidden_specs_are_not_silently_ignored(tool, inputs, spec):
    result = Observation([ToolCall(tool, inputs)], [], "", {})
    with pytest.raises(AssertionError):
        assert_observation(result, {"forbidden_invocations": [spec]})

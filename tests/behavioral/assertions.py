"""Assertion helpers for behavioral tests."""

import re

from .runner import Observation, ToolCall


def _call_matches(call: ToolCall, spec: dict) -> bool:
    call_type = spec.get("type")
    if call.name != call_type and not (call_type == "Agent" and call.name == "Task"):
        return False
    if call_type == "Skill" and "name" in spec:
        return call.input.get("skill") == spec["name"]
    if call_type == "Agent" and "subagent_type" in spec:
        return call.input.get("subagent_type") == spec["subagent_type"]
    return True


def assert_required_invocations(calls: list[ToolCall], required: list[dict]) -> None:
    """Assert that every entry in `required` appears at least once in `calls` (order-insensitive)."""
    missing = []
    for spec in required:
        if not any(_call_matches(c, spec) for c in calls):
            missing.append(spec)

    if missing:
        call_summary = [(c.name, c.input) for c in calls]
        raise AssertionError(
            f"Missing required invocations: {missing}\n"
            f"Actual calls ({len(calls)}): {call_summary}"
        )


def assert_expected_sequence(calls: list[ToolCall], sequence: list[dict]) -> None:
    """Assert that `sequence` appears as a subsequence within `calls` (other calls allowed between)."""
    it = iter(calls)
    for spec in sequence:
        matched = False
        for call in it:
            if _call_matches(call, spec):
                matched = True
                break
        if not matched:
            call_summary = [(c.name, c.input) for c in calls]
            raise AssertionError(
                f"Expected sequence step not found: {spec}\n"
                f"Actual calls ({len(calls)}): {call_summary}"
            )


def assert_observation(observation: Observation, expected: dict) -> None:
    """Check captured output/bytes, not a model's claim of artifact existence."""
    for phrase in expected.get("final_contains", []):
        assert phrase in observation.final_output, (phrase, observation.final_output)
    for relative, text in expected.get("artifacts", {}).items():
        assert relative in observation.artifacts, f"Artifact not captured: {relative}"
        actual = observation.artifacts[relative]
        assert actual == (text.encode() if text is not None else None), (relative, actual, text)
    for relative, phrases in expected.get("artifact_contains", {}).items():
        assert relative in observation.artifacts, f"Artifact not captured: {relative}"
        actual = observation.artifacts[relative]
        assert actual is not None, f"Artifact was not produced: {relative}"
        contents = actual.decode("utf-8")
        for phrase in phrases:
            assert phrase in contents, (relative, phrase, contents)
    for spec in expected.get("forbidden_invocations", []):
        assert not any(_call_matches(call, spec) for call in observation.calls), spec
    for call in observation.calls:
        if call.name not in {"Agent", "Task", "spawn_agent", "task"}:
            continue
        brief = "\n".join(
            value for key in ("description", "prompt", "message")
            if isinstance(value := call.input.get(key), str)
        )
        roles = set(re.findall(r"\[nstack role=([a-z-]+)(?:\s|])", brief))
        assert not roles.intersection(expected.get("forbidden_roles", [])), (call.name, roles)

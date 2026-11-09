"""Assertion helpers for behavioral tests."""

from .runner import ToolCall


def _call_matches(call: ToolCall, spec: dict) -> bool:
    call_type = spec.get("type")
    if call.name != call_type:
        return False
    if call_type == "Skill":
        return call.input.get("skill") == spec.get("name")
    if call_type == "Agent":
        return call.input.get("subagent_type") == spec.get("subagent_type")
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

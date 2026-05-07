"""Assertion helpers for behavioural tests."""

from __future__ import annotations

from .judge import JudgeVerdict


def assert_judge_verdicts(verdicts: list[JudgeVerdict]) -> None:
    """Raise AssertionError listing every FAIL with its rationale.

    Passes silently when all verdicts are PASS.
    """
    failures = [v for v in verdicts if v.verdict != "PASS"]
    if not failures:
        return

    lines = ["Judge returned FAIL for the following rubric items:"]
    for v in failures:
        lines.append(f"  - {v.criterion}")
        lines.append(f"    rationale: {v.rationale}")
    raise AssertionError("\n".join(lines))

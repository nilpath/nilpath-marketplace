"""Prove copied content differs only at recorded operator-approved substitutions."""

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/pstack-port.json").read_text())
FILES = FIXTURE["files"]


@pytest.mark.parametrize("relative", sorted(FILES))
def test_reversing_recorded_substitutions_restores_exact_upstream_bytes(relative):
    record = FILES[relative]
    text = (ROOT / relative).read_text()
    for change in reversed(record["changes"]):
        before, after = change["before"], change["after"]
        positions = change["output_positions"]
        assert len(positions) == change["count"]
        for position in reversed(positions):
            assert text[position:position + len(after)] == after, (relative, change)
            text = text[:position] + before + text[position + len(after):]
    assert hashlib.sha256(text.encode()).hexdigest() == record["sha256"]


@pytest.mark.parametrize("harness", ("claude", "copilot", "codex"))
def test_copied_helpers_are_identical_except_the_approved_scheduling_marker(harness):
    prefix = "src/plugins/nstack/skills/nstack-flow/scripts/"
    for relative, record in FILES.items():
        if not relative.startswith(prefix):
            continue
        source = ROOT / relative
        suffix = relative.removeprefix("src/plugins/nstack/")
        target = ROOT / f"dist/{harness}/plugins/nstack" / suffix.removesuffix(".j2")
        if not relative.endswith(".j2"):
            assert record["changes"] == []
            assert source.read_bytes() == target.read_bytes()
        else:
            assert record["upstream_path"] in ("scripts/check-plan.mjs", "scripts/check-plan.test.ts")
            assert len(record["changes"]) == 1
            change = record["changes"][0]
            assert change["before"] == "/loop 1h"
            marker = "/loop 1h" if harness == "claude" else "native recurring automation every 1h"
            assert source.read_text().replace(change["after"], marker) == target.read_text()


def test_port_inventory_is_pinned_and_contains_only_the_selected_playbooks_and_helpers():
    assert FIXTURE["upstream_commit"] == "8b3326d99fd4b993cb33a24dad8af03175c642c5"
    playbooks = {record["upstream_path"] for record in FILES.values() if record["upstream_path"].startswith("playbooks/")}
    assert playbooks == {
        f"playbooks/{name}.md" for name in (
            "babysit", "eval", "hillclimb", "multi-phase-plan", "opening-a-pr",
            "orchestrate", "pause-safely", "perf-issue", "prototype", "refactoring",
            "session-pickup", "worktree-cleanup",
        )
    }
    triage = FILES["src/plugins/nstack/skills/nstack-flow/references/review-triage.md.j2"]
    assert triage["upstream_path"] == "references/bugbot-triage.md"
    assert len(FILES) == 34

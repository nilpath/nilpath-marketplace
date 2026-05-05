"""Behavioral tests: invoke Claude CLI and assert skill/agent invocation sequences."""

from pathlib import Path
import yaml
import pytest
from behavioral.runner import run_skill_test
from behavioral.assertions import assert_required_invocations, assert_expected_sequence

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "behavioral"
PLUGIN_DIR = Path(__file__).parent.parent / "plugins" / "claude-code-tools"


def _collect_fixtures() -> list[Path]:
    if not FIXTURES_DIR.exists():
        return []
    return sorted(p for p in FIXTURES_DIR.iterdir() if p.is_dir())


@pytest.mark.behavioral
@pytest.mark.parametrize("fixture_dir", _collect_fixtures(), ids=lambda p: p.name)
def test_behavioral(fixture_dir: Path):
    prompt_file = fixture_dir / "prompt.md"
    expectations_file = fixture_dir / "expectations.yaml"
    context_dir = fixture_dir / "context"

    assert prompt_file.exists(), f"Missing prompt.md in {fixture_dir.name}"
    assert expectations_file.exists(), f"Missing expectations.yaml in {fixture_dir.name}"

    prompt = prompt_file.read_text().strip()
    expectations = yaml.safe_load(expectations_file.read_text())

    calls = run_skill_test(
        prompt=prompt,
        context_dir=context_dir if context_dir.exists() else None,
        plugin_dir=PLUGIN_DIR,
    )

    if required := expectations.get("required_invocations"):
        assert_required_invocations(calls, required)

    if sequence := expectations.get("expected_sequence"):
        assert_expected_sequence(calls, sequence)

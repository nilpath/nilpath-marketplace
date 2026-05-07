"""Per-skill behavioural tests with LLM-as-judge.

For every skill under plugins/claude-code-tools/skills/ that ships a tests.yaml,
this module emits two kinds of parametrized tests:

- test_skill_invocation: positive/negative prompts checking the skill is (or isn't)
  invoked according to its frontmatter description.
- test_skill_instructions_followed: prompts that exercise the skill's body, judged
  against a multi-item rubric.

Each case is rendered to its own pytest id of the form `<skill>:<case-name>`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from behavioral.assertions import assert_judge_verdicts
from behavioral.judge import run_judge
from behavioral.runner import run_skill_test

PLUGIN_DIR = Path(__file__).parent.parent / "plugins" / "claude-code-tools"
SKILLS_DIR = PLUGIN_DIR / "skills"


def _load_skill_tests(skill_dir: Path) -> dict | None:
    tests_file = skill_dir / "tests.yaml"
    if not tests_file.exists():
        return None
    return yaml.safe_load(tests_file.read_text()) or {}


def _collect_invocation_cases() -> list[pytest.param]:
    cases = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        data = _load_skill_tests(skill_dir)
        if not data:
            continue
        invocation = data.get("invocation") or {}
        for kind in ("positive", "negative"):
            for case in invocation.get(kind) or []:
                case_id = f"{skill_dir.name}:{kind}:{case['name']}"
                cases.append(pytest.param(skill_dir.name, case, id=case_id))
    return cases


def _collect_instructions_cases() -> list[pytest.param]:
    cases = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        data = _load_skill_tests(skill_dir)
        if not data:
            continue
        for case in data.get("instructions") or []:
            case_id = f"{skill_dir.name}:{case['name']}"
            cases.append(pytest.param(skill_dir.name, case, id=case_id))
    return cases


@pytest.mark.behavioral
@pytest.mark.parametrize("skill_name, case", _collect_invocation_cases())
def test_skill_invocation(skill_name: str, case: dict):
    transcript = run_skill_test(
        prompt=case["prompt"],
        inline_context=case.get("context"),
        plugin_dir=PLUGIN_DIR,
    )
    verdicts = run_judge(transcript, [case["expectation"]])
    assert_judge_verdicts(verdicts)


@pytest.mark.behavioral
@pytest.mark.parametrize("skill_name, case", _collect_instructions_cases())
def test_skill_instructions_followed(skill_name: str, case: dict):
    transcript = run_skill_test(
        prompt=case["prompt"],
        inline_context=case.get("context"),
        plugin_dir=PLUGIN_DIR,
    )
    rubric = case["expectation"]
    if isinstance(rubric, str):
        rubric = [rubric]
    verdicts = run_judge(transcript, rubric)
    assert_judge_verdicts(verdicts)

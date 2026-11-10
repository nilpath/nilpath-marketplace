from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from buildkit.config import load_config
from buildkit.render import make_environment, render_file


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/plugins/nstack/skills/nstack-flow/scripts/check_plan.py.j2"
FIXTURES = ROOT / "tests/fixtures/nstack-python/checker"


def valid_plan(cadence: str = "/loop 1h") -> str:
    return (FIXTURES / "valid.input").read_text().replace("/loop 1h", cadence)


def render_checker(tmp_path: Path, harness: str) -> Path:
    config = load_config(ROOT)
    rendered = render_file(
        make_environment(), SOURCE, config.harnesses[harness], config,
        skill_name="nstack-flow",
    )
    path = tmp_path / f"check_plan_{harness}.py"
    path.write_text(rendered, encoding="utf-8")
    return path


@pytest.fixture
def checker(tmp_path: Path) -> Path:
    return render_checker(tmp_path, "claude")


def run(checker: Path, plan: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(checker), str(plan), *extra],
        capture_output=True, text=True, check=False,
    )


@pytest.mark.parametrize("harness", ("claude", "copilot", "codex"))
def test_harness_requires_its_rendered_cadence(tmp_path: Path, harness: str) -> None:
    checker = render_checker(tmp_path, harness)
    cadence = "/loop 1h" if harness == "claude" else "native recurring automation every 1h"
    other = "native recurring automation every 1h" if harness == "claude" else "/loop 1h"
    plan = tmp_path / "plan.md"
    plan.write_text(valid_plan(cadence))
    assert run(checker, plan).returncode == 0
    plan.write_text(valid_plan(other))
    result = run(checker, plan)
    assert result.returncode == 1
    assert f'Program checklist lacks "{cadence}"' in result.stderr


def test_missing_path_has_usage_and_exit_two(checker: Path) -> None:
    result = subprocess.run([sys.executable, str(checker)], capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "Usage: python3 check_plan.py <plan.md>\n"


def test_accepts_valid_plan_and_ignores_extra_arguments(checker: Path, tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(valid_plan())
    result = run(checker, plan, "ignored", "also-ignored")
    assert result.returncode == 0
    assert result.stdout == "PR 1  boxes=19  files=1 build=1 you-see=1 verify-unit=1 verify-live=10 verify-perf=4 review-gate=0 merge=1\n1 PR sections, 0 problems\n"
    assert result.stderr == ""


@pytest.mark.parametrize(
    "suffix",
    [
        "```markdown\n## Example only\n```\n",
        " ```markdown\n## Example only\n ```\n",
        "  ```markdown\n## Example only\n  ```\n",
        "   ```markdown\n## Example only\n   ```\n",
        "```markdown\n## Example only\n````\n",
        "````markdown\n```markdown\n## Example only\n```\n````\n",
        "~~~markdown `info`\n## Example only\n ~~~\n",
        "````markdown\n~~~\n## Example only\n````\n",
        "````markdown\n```\n## Example only\n````\n",
        "````markdown\n``` info\n## Example only\n````\n",
    ],
)
def test_ports_all_upstream_fence_acceptance_cases(checker: Path, tmp_path: Path, suffix: str) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(valid_plan() + suffix)
    assert run(checker, plan).returncode == 0


@pytest.mark.parametrize("suffix", ["  ", "\t"])
def test_ports_upstream_rejected_suffixed_closers(checker: Path, tmp_path: Path, suffix: str) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(valid_plan() + f"```markdown\n## Example only\n```{suffix}\n## Example only\n")
    result = run(checker, plan)
    assert result.returncode == 1
    assert '"## Example only" after Close the program is not an appendix' in result.stderr


@pytest.mark.parametrize(
    ("suffix", "diagnostic"),
    [
        ("```markdown\nThis prose has a mid-sentence colon: inside code\n```\nThis prose has a mid-sentence colon: bad.\n", "mid-sentence colon"),
        ("```markdown `invalid`\n## Example only\n```\n", '"## Example only" after Close the program is not an appendix'),
    ],
)
def test_ports_upstream_rejection_cases(checker: Path, tmp_path: Path, suffix: str, diagnostic: str) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(valid_plan() + suffix)
    result = run(checker, plan)
    assert result.returncode == 1
    assert diagnostic in result.stderr


def test_frontmatter_crlf_bom_and_unicode_digits_preserve_lexical_rules(checker: Path, tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    text = "---\r\nkey: value\r\n---\r\n" + valid_plan().replace("Lane 10.", "Lane ١٠.")
    plan.write_bytes(b"\xef\xbb\xbf" + text.encode())
    result = run(checker, plan)
    assert result.returncode == 1
    assert "lanes are [1,2,3,4,5,6,7,8,9], expected 1 to 10" in result.stderr
    assert "live box is not a lane" in result.stderr


def test_large_lane_numbers_use_javascript_number_display(checker: Path, tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(valid_plan().replace("Lane 10.", "Lane 1000000000000000000000."))
    result = run(checker, plan)
    assert result.returncode == 1
    assert "lanes are [1,2,3,4,5,6,7,8,9,1e+21], expected 1 to 10" in result.stderr


@pytest.mark.parametrize(
    "name",
    ("minimal", "valid", "trim-and-colon", "line-terminators", "crlf-final-cr"),
)
def test_pinned_node_oracle_fixtures(checker: Path, tmp_path: Path, name: str) -> None:
    plan = tmp_path / "plan.md"
    contents = (FIXTURES / f"{name}.input").read_bytes()
    plan.write_bytes(contents)
    result = run(checker, plan)
    expected = json.loads((FIXTURES / f"{name}.expected.json").read_text())
    assert result.returncode == expected["exit"]
    assert result.stdout == expected["stdout"].replace("<PLAN>", str(plan))
    assert result.stderr == expected["stderr"].replace("<PLAN>", str(plan))

"""CI gate: the committed harness output must match a fresh build of src/."""

from pathlib import Path

from buildkit.build import check
from buildkit.validate import validate_sources

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_generated_output_matches_sources():
    diffs = check(REPO_ROOT)
    assert not diffs, (
        "Generated output drifted from src/ — run `make build` and commit:\n"
        + "\n".join(diffs)
    )


def test_sources_are_valid():
    errors = validate_sources(REPO_ROOT)
    assert not errors, "\n".join(errors)

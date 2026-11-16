"""Validate fresh source output without changing the installation snapshot."""

from pathlib import Path
import os
import shutil
import subprocess
import sys

from buildkit.validate import validate_sources
from paths import RENDERED_ROOT

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_generated_tests_use_a_fresh_temporary_tree():
    assert not RENDERED_ROOT.is_relative_to(REPO_ROOT)
    assert (RENDERED_ROOT / "dist/claude/plugins/git-tools/skills/git-commits/SKILL.md").is_file()


def test_preview_contains_source_only_changes_and_preserves_committed_output(tmp_path):
    shutil.copytree(REPO_ROOT / "src", tmp_path / "src")
    (tmp_path / "tests").mkdir()
    shutil.copy(REPO_ROOT / "tests/paths.py", tmp_path / "tests/paths.py")
    source = tmp_path / "src/plugins/git-tools/skills/git-commits/SKILL.md.j2"
    source.write_text(source.read_text() + "\nFresh source-only guidance.\n")
    relative = "dist/claude/plugins/git-tools/skills/git-commits/SKILL.md"
    committed = tmp_path / relative
    committed.parent.mkdir(parents=True)
    committed.write_text("Released installation snapshot.\n")
    script = (
        "from paths import RENDERED_ROOT\n"
        f"print((RENDERED_ROOT / {relative!r}).read_text().splitlines()[-1])\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, text=True, capture_output=True,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "tests") + os.pathsep
             + str(REPO_ROOT / "tools/buildkit/src")},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "Fresh source-only guidance.\n"
    assert committed.read_text() == "Released installation snapshot.\n"


def test_sources_are_valid():
    errors = validate_sources(REPO_ROOT)
    assert not errors, "\n".join(errors)

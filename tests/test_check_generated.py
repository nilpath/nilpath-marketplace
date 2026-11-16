from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("change", ["source", "source-lookalike", "generated", "invalid-base"])
def test_generated_check_uses_only_shell_and_git(tmp_path, change):
    (tmp_path / "tools").mkdir()
    shutil.copy(ROOT / "tools/check_generated.sh", tmp_path / "tools/check_generated.sh")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    commit = ["git", "-c", "user.name=Tester", "-c", "user.email=test@example.com", "commit", "-qm", "chore: fixture"]
    subprocess.run(commit, cwd=tmp_path, check=True)
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    path = tmp_path / {
        "generated": "dist/file",
        "source-lookalike": " dist/file",
    }.get(change, "source.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("changed\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(commit, cwd=tmp_path, check=True)
    result = subprocess.run(
        ["sh", "tools/check_generated.sh", "missing-base" if change == "invalid-base" else base],
        cwd=tmp_path, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"},
    )
    if change in {"source", "source-lookalike"}:
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""
    elif change == "generated":
        assert result.returncode == 1
        assert result.stdout == "dist/file\n"
    else:
        assert result.returncode != 0
        assert "missing-base" in result.stderr

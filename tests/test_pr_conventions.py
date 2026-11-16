import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/pr_conventions.sh"


@pytest.mark.parametrize("title,expected", [
    ("feat(nstack): add a verification skill", 0),
    ("fix: correct release planning", 0),
    ("feat!: remove legacy behavior", 0),
    ("refactor(git-tools)!: change command arguments", 0),
    ("chore(release): prepare component releases", 0),
    ("deps: update git-cliff", 0),
    ("docs: clarify caf\u00e9 examples", 0),
    ("Add a feature", 1),
    ("unknown: add a feature", 1),
    ("feat(): empty scope", 1),
    ("feat(bad scope): invalid scope", 1),
    ("feat: ", 1),
    ("feat:   ", 1),
    ("feat:no space", 1),
    ("feat!!: repeated marker", 1),
    ("feat: valid\ninvalid second line", 1),
    ("feat: trailing newline\n", 1),
    ("feat: embedded\rcarriage return", 1),
    ("", 1),
])
def test_title_validation(title, expected):
    result = subprocess.run([str(SCRIPT), "--title", title], capture_output=True, text=True)
    assert result.returncode == expected
    if expected:
        assert "ERROR: PR title is not a Conventional Commit." in result.stderr
        assert "Retitle the PR" in result.stderr
    else:
        assert result.stdout == "OK: title is a Conventional Commit\n"


@pytest.mark.parametrize("args", [[], ["--title"], ["--unknown", "fix: valid"], ["--title", "fix: valid", "extra"]])
def test_invalid_invocation_fails_without_fetching(args):
    env = {key: value for key, value in os.environ.items() if key != "PR_NUMBER"}
    result = subprocess.run([str(SCRIPT), *args], env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert result.stderr


@pytest.mark.parametrize("token_env", [{}, {"GITHUB_TOKEN": "test-token"}, {
    "GITHUB_TOKEN": "fallback-token", "GH_TOKEN": "preferred-token",
}])
def test_fetch_uses_read_only_api_without_changing_login(tmp_path, token_env):
    gh = tmp_path / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['CALL_LOG']).write_text(json.dumps([sys.argv[1:], os.environ.get('GH_TOKEN')]))\n"
        "print('fix(nstack): correct instructions')\n"
    )
    gh.chmod(0o755)
    log = tmp_path / "call.json"
    env = {key: value for key, value in os.environ.items() if key not in {"GH_TOKEN", "GITHUB_TOKEN"}}
    env.update(token_env, PATH=f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
               CALL_LOG=str(log), PR_NUMBER="123", GH_REPO="nilpath/nilpath-marketplace")
    result = subprocess.run([str(SCRIPT)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(log.read_text()) == [
        ["api", "--hostname", "github.com", "repos/nilpath/nilpath-marketplace/pulls/123", "--jq", ".title"],
        token_env.get("GH_TOKEN", token_env.get("GITHUB_TOKEN", "")),
    ]


def test_fetch_failure_is_not_reported_as_success(tmp_path):
    gh = tmp_path / "gh"
    gh.write_text("#!/bin/sh\nprintf 'API unavailable\\n' >&2\nexit 7\n")
    gh.chmod(0o755)
    result = subprocess.run([str(SCRIPT)], capture_output=True, text=True,
                            env={**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
                                 "PR_NUMBER": "123"})
    assert result.returncode == 7
    assert result.stderr == "API unavailable\n"
    assert "OK:" not in result.stdout


def test_title_is_treated_as_data(tmp_path):
    marker = tmp_path / "injected"
    title = f"feat: $(touch {marker})"
    result = subprocess.run([str(SCRIPT), "--title", title], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "OK: title is a Conventional Commit\n"
    assert not marker.exists()

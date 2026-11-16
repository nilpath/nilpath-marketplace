import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

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


def test_workflow_handles_title_edits_and_passes_title_as_data(tmp_path):
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]["pull_request"]["types"]) >= {"opened", "synchronize", "reopened", "edited"}
    job = workflow["jobs"]["pr-title"]
    assert job["if"] == "github.event_name == 'pull_request'"
    step = job["steps"][-1]
    assert step["env"]["PR_TITLE"] == "${{ github.event.pull_request.title }}"
    marker = tmp_path / "injected"
    title = f"feat: $(touch {marker})"
    result = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=ROOT, capture_output=True,
                            text=True, env={**os.environ, "PR_TITLE": title})
    assert result.returncode == 0, result.stderr
    assert result.stdout == "OK: title is a Conventional Commit\n"
    assert not marker.exists()


def test_ci_checks_artifact_ownership_before_preview_rendering():
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["test-static"]["steps"]
    gate = next(i for i, step in enumerate(steps) if "check-pr --base-sha" in step.get("run", ""))
    preview = next(i for i, step in enumerate(steps) if "make test-static" in step.get("run", ""))
    assert gate < preview
    assert steps[gate]["if"] == "github.event_name == 'pull_request'"
    assert steps[gate]["env"]["BASE_SHA"] == "${{ github.event.pull_request.base.sha }}"


def test_writer_consumes_only_the_read_only_verifier_dependency():
    workflow = yaml.load((ROOT / ".github/workflows/release.yml").read_text(), Loader=yaml.BaseLoader)
    verify, writer = (workflow["jobs"][name] for name in ("verify", "write"))
    assert verify["needs"] == "inspect"
    assert verify["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert writer["needs"] == "verify"
    download = next(step for step in writer["steps"] if step.get("uses", "").startswith("actions/download-artifact@"))
    assert download["with"]["artifact-ids"] == "${{ needs.verify.outputs.artifact_id }}"
    write = writer["steps"][-1]
    assert write["env"]["VERIFICATION_ARTIFACT_ID"] == "${{ needs.verify.outputs.artifact_id }}"
    assert "--verification-artifact-id" in write["run"]
    assert not any("make build" in step.get("run", "") for step in workflow["jobs"]["inspect"]["steps"])
    candidate_steps = [step for step in workflow["jobs"]["inspect"]["steps"]
                       if step.get("working-directory") == "candidate"]
    assert all(step["if"] == "steps.snapshot.outputs.kind == 'proposal'" for step in candidate_steps)
    historical = next(step for step in workflow["jobs"]["inspect"]["steps"]
                      if step.get("if") == "steps.snapshot.outputs.kind == 'drafts'")
    assert "python -S dispatcher/tools/release.py bundle --root candidate" in historical["run"]

import json
import os
from pathlib import Path
import shutil
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
    step = next(step for step in job["steps"] if step.get("name") == "Check Conventional Commit title")
    assert step["env"]["PR_TITLE"] == "${{ github.event.pull_request.title }}"
    marker = tmp_path / "injected"
    title = f"feat: $(touch {marker})"
    result = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=ROOT, capture_output=True,
                            text=True, env={**os.environ, "PR_TITLE": title})
    assert result.returncode == 0, result.stderr
    assert result.stdout == "OK: title is a Conventional Commit\n"
    assert not marker.exists()


def test_ci_checks_generated_ownership_once_alongside_title_validation():
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    jobs = workflow["jobs"]
    guards = [(job, step) for job, config in jobs.items() for step in config["steps"]
              if "tools/check_generated.py" in step.get("run", "")]
    assert [job for job, _ in guards] == ["pr-title"]
    assert guards[0][1]["name"] == "Check generated-file ownership"
    assert guards[0][1]["env"]["BASE_SHA"] == "${{ github.event.pull_request.base.sha }}"
    checkout = next(step for step in jobs["pr-title"]["steps"] if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["fetch-depth"] == "0"
    assert checkout["with"]["ref"] == "${{ github.event.pull_request.head.sha }}"
    release_checks = [job for job, config in jobs.items() for step in config["steps"]
                      if "tools/release.py check-pr" in step.get("run", "")]
    assert release_checks == ["release-plan"]
    test_commands = [step["run"] for step in jobs["test-static"]["steps"] if "run" in step]
    assert test_commands == [
        'make install VENV="$RUNNER_TEMP/nilpath-ci"',
        'make test-static VENV="$RUNNER_TEMP/nilpath-ci"',
    ]


@pytest.mark.parametrize("change", ["source", "source-lookalike", "generated", "head-mismatch"])
def test_ci_generated_check_works_without_release_tool_or_site_packages(tmp_path, change):
    for path in ("tools/check_generated.py", "tools/buildkit/src/buildkit/__init__.py",
                 "tools/buildkit/src/buildkit/ownership.py"):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / path, target)
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
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    event = tmp_path / "event.json"
    event.write_text(json.dumps({
        "repository": {"full_name": "nilpath/test"},
        "pull_request": {"user": {"login": "human", "id": 1},
                         "head": {"sha": base if change == "head-mismatch" else head}},
    }))
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    step = next(step for step in workflow["jobs"]["pr-title"]["steps"]
                if "tools/check_generated.py" in step.get("run", ""))
    result = subprocess.run(
        ["bash", "-e", "-c", step["run"]], cwd=tmp_path, capture_output=True, text=True,
        env={"PATH": os.pathsep.join([str(Path(sys.executable).parent), "/usr/bin", "/bin"]),
             "BASE_SHA": base, "GITHUB_EVENT_PATH": str(event)},
    )
    if change in {"source", "source-lookalike"}:
        assert result.returncode == 0, result.stderr
        assert result.stdout == "Ordinary PR preserves build-owned paths.\n"
    elif change == "generated":
        assert result.returncode == 1
        assert result.stderr == "check-generated: Ordinary PR changes build-owned paths:\ndist/file\n"
    else:
        assert result.returncode == 1
        assert result.stderr == "check-generated: PR head mismatch\n"


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

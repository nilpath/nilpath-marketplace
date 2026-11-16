"""Local CLI contract tests. Every subprocess gh is a temporary fake on PATH."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src/plugins/nstack/skills/nstack-flow/scripts/reply_thread.py"
)
BODY = 'Tack, räven 🦊.\r\n  Keep "quotes", `code`, $(touch NEVER), and ; echo no.\r\n'
FORMATTED = '🤖 Automated post by `nstack`.\n\n' + BODY
PUBLIC_PR = "https://api.github.com/repos/acme/widgets/pulls/48"

FAKE_GH = r'''
import json
import os
import sys
from pathlib import Path

log = Path(os.environ["REPLY_CALLS"])
calls = log.read_text().splitlines() if log.exists() else []
stdin = sys.stdin.read()
with log.open("a") as output:
    output.write(json.dumps({
        "argv": sys.argv[1:], "stdin": stdin, "cwd": os.getcwd(),
        "env_probe": os.environ.get("REPLY_ENV_PROBE"),
        "gh_host": os.environ.get("GH_HOST"),
    }) + "\n")
step = json.loads(Path(os.environ["REPLY_PLAN"]).read_text())[len(calls)]
response = step.get("json")
if step.get("echo_body"):
    response["body"] = json.loads(stdin)["body"]
sys.stdout.write(step["stdout"] if "stdout" in step else json.dumps(response))
sys.stderr.write(step.get("stderr", ""))
sys.exit(step.get("returncode", 0))
'''


def _steps(canonical=PUBLIC_PR, html_url="https://github.com/acme/widgets/pull/48#discussion_r456"):
    return [
        {"json": {"id": 123, "pull_request_url": canonical}},
        {"json": {"number": 48, "url": canonical}},
        {
            "json": {
                "id": 456, "html_url": html_url, "user": {"login": "actual-poster"},
                "in_reply_to_id": 123, "pull_request_url": canonical,
            },
            "echo_body": True,
        },
    ]


def _top_level_steps(issue_url="https://git.corp/api/v3/repos/acme/widgets/issues/48"):
    return [
        {"json": {"number": 48, "issue_url": issue_url}},
        {
            "json": {
                "id": 789, "html_url": "https://git.corp/acme/widgets/pull/48#issuecomment-789",
                "user": {"login": "actual-poster"}, "issue_url": issue_url,
            },
            "echo_body": True,
        },
    ]


@pytest.fixture
def cli(tmp_path):
    script = tmp_path / "reply_thread.py"
    shutil.copyfile(SOURCE, script)
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    fake = binary_dir / "gh"
    fake.write_text(f"#!{sys.executable}\n" + FAKE_GH, encoding="utf-8")
    fake.chmod(0o755)
    body = tmp_path / "reply.md"
    body.write_bytes(BODY.encode("utf-8"))
    plan = tmp_path / "plan.json"
    calls = tmp_path / "calls.jsonl"
    env = os.environ.copy()
    env.pop("GH_HOST", None)
    env.update(
        PATH=str(binary_dir), REPLY_PLAN=str(plan), REPLY_CALLS=str(calls),
        REPLY_ENV_PROBE="inherited-without-auth-inspection",
    )
    return {"script": script, "body": body, "plan": plan, "calls": calls, "env": env, "cwd": tmp_path}


def _run(cli, steps=None, *, hostname=None, gh_host=None, extra=(), selector=("--comment-id", "123")):
    cli["plan"].write_text(json.dumps(_steps() if steps is None else steps), encoding="utf-8")
    env = cli["env"].copy()
    if gh_host is not None:
        env["GH_HOST"] = gh_host
    argv = [
        sys.executable, "-I", "-S", "-B", str(cli["script"]),
        "--repo", "acme/widgets", "--pr", "48", *selector,
        "--body-file", str(cli["body"]),
    ]
    if hostname is not None:
        argv.extend(["--hostname", hostname])
    process = subprocess.run(
        [*argv, *extra], cwd=cli["cwd"], env=env,
        capture_output=True, text=True, timeout=10,
    )
    assert process.stderr == ""
    assert len(process.stdout.splitlines()) == 1
    return process.returncode, json.loads(process.stdout)


def _raw_run(cli, args):
    return subprocess.run(
        [sys.executable, "-I", "-S", "-B", str(cli["script"]), *args],
        cwd=cli["cwd"], env=cli["env"], capture_output=True, text=True, timeout=10,
    )


def _calls(cli):
    if not cli["calls"].exists():
        return []
    return [json.loads(line) for line in cli["calls"].read_text().splitlines()]


@pytest.fixture
def helper(cli, monkeypatch):
    spec = importlib.util.spec_from_file_location("reply_thread_under_test", cli["script"])
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setenv("PATH", cli["env"]["PATH"])
    return module


@pytest.mark.parametrize(
    "hostname,gh_host,selected,canonical,html_url",
    [
        ("github.com", "ignored.internal", "github.com", PUBLIC_PR,
         "https://github.com/acme/widgets/pull/48#discussion_r456"),
        (None, "git.corp:8443", "git.corp:8443",
         "https://git.corp:8443/api/v3/repos/acme/widgets/pulls/48",
         "https://git.corp:8443/acme/widgets/pull/48#discussion_r456"),
        (None, None, "github.com", PUBLIC_PR,
         "https://github.com/acme/widgets/pull/48#discussion_r456"),
        ("octo.ghe.com", "ignored.internal", "octo.ghe.com",
         "https://api.octo.ghe.com/repos/acme/widgets/pulls/48",
         "https://octo.ghe.com/acme/widgets/pull/48#discussion_r456"),
    ],
)
def test_isolated_cli_pins_host_and_preserves_exact_body(
    cli, hostname, gh_host, selected, canonical, html_url,
):
    code, result = _run(cli, _steps(canonical, html_url), hostname=hostname, gh_host=gh_host)
    assert code == 0
    assert result == {
        "ok": True, "outcome": "posted", "hostname": selected,
        "repo": "acme/widgets", "pr": 48, "root_comment_id": 123,
        "reply": {"id": 456, "html_url": html_url, "user": {"login": "actual-poster"}},
    }
    calls = _calls(cli)
    assert [call["argv"] for call in calls] == [
        ["api", "--hostname", selected, "--method", "GET", "repos/acme/widgets/pulls/comments/123"],
        ["api", "--hostname", selected, "--method", "GET", "repos/acme/widgets/pulls/48"],
        [
            "api", "--hostname", selected, "--method", "POST",
            "repos/acme/widgets/pulls/48/comments/123/replies", "--input", "-",
        ],
    ]
    assert [call["stdin"] for call in calls[:2]] == ["", ""]
    assert json.loads(calls[2]["stdin"]) == {"body": FORMATTED}
    assert [(call["cwd"], call["env_probe"], call["gh_host"]) for call in calls] == [
        (str(cli["cwd"]), "inherited-without-auth-inspection", gh_host)
    ] * 3
    assert cli["body"].read_bytes() == BODY.encode("utf-8")
    assert not (cli["cwd"] / "NEVER").exists()


def test_hostname_validation_allows_private_names_and_port_boundaries(helper):
    for hostname in ["git", "localhost:1", "git.corp:65535", "GHE-1.internal:443", "127.0.0.1:8080"]:
        assert helper.validate_hostname(hostname) == hostname
    for hostname in [
        "", "--help", "-git.corp", "https://git.corp", "git.corp/api/v3", "u@git.corp",
        "git.corp?q=x", "git.corp#part", "git corp", "git.corp\n", "git.\x00corp",
        "git..corp", "git-.corp", "git.corp:", "git.corp:abc", "git.corp:0",
        "git.corp:65536", "git.corp:-1", "git.corp:1:2",
    ]:
        with pytest.raises(ValueError):
            helper.validate_hostname(hostname)


@pytest.mark.parametrize("hostname,gh_host", [("", "good.internal"), (None, ""), ("bad/host", None)])
def test_invalid_selected_host_never_calls_gh(cli, hostname, gh_host):
    code, result = _run(cli, hostname=hostname, gh_host=gh_host)
    assert (code, result["ok"], result["outcome"], result["error"]["code"]) == (
        1, False, "not_attempted", "invalid_input",
    )
    assert result["hostname"] == (hostname if hostname is not None else gh_host)
    assert _calls(cli) == []


def test_attribution_replaces_only_own_exact_leading_banners(helper):
    old = "🤖 Automated post by `nstack`, model `observed-old`.\r\n\r\n"
    stacked = "🤖 Automated post by `nstack`.\n\n" + old + BODY
    expected = "🤖 Automated post by `nstack`, model `observed-now`.\n\n" + BODY
    assert helper.attributed_body(stacked, "observed-now") == expected
    assert helper.attributed_body(expected, "observed-now") == expected
    assert helper.attributed_body(expected) == FORMATTED
    human = "🤖 Automated post by `a-person`.\n\n" + BODY
    assert helper.attributed_body(human) == "🤖 Automated post by `nstack`.\n\n" + human
    not_exact = "🤖 Automated post by `nstack`.\nNo blank separator.\n"
    assert helper.attributed_body(not_exact) == "🤖 Automated post by `nstack`.\n\n" + not_exact
    for text in ["", " \r\n\t", "🤖 Automated post by `nstack`.", old + " \r\n"]:
        with pytest.raises(ValueError, match="nonblank prose"):
            helper.attributed_body(text)
    for model in ["", " ", "bad`model", "a\nb", "a\rb", "a\tb", "a\x00b", "a\u2028b", "a\u202eb"]:
        with pytest.raises(ValueError, match="Model"):
            helper.attributed_body(BODY, model)


def test_cli_accepts_caller_supplied_model_without_looking_it_up(cli):
    cli["body"].write_bytes(("🤖 Automated post by `nstack`.\n\n" + BODY).encode("utf-8"))
    code, result = _run(cli, extra=["--model", "actually-observed"])
    assert (code, result["outcome"]) == (0, "posted")
    assert json.loads(_calls(cli)[2]["stdin"])["body"] == (
        "🤖 Automated post by `nstack`, model `actually-observed`.\n\n" + BODY
    )


def test_top_level_enterprise_flow_uses_canonical_issue_url_and_exact_body(cli):
    issue_url = "https://enterprise.internal/api/v3/repos/acme/widgets/issues/48"
    code, result = _run(
        cli, _top_level_steps(issue_url), hostname="enterprise.internal", selector=("--top-level",),
    )
    assert (code, result) == (
        0,
        {
            "ok": True, "outcome": "posted", "hostname": "enterprise.internal",
            "repo": "acme/widgets", "pr": 48,
            "reply": {
                "id": 789, "html_url": "https://git.corp/acme/widgets/pull/48#issuecomment-789",
                "user": {"login": "actual-poster"},
            },
        },
    )
    assert [call["argv"] for call in _calls(cli)] == [
        ["api", "--hostname", "enterprise.internal", "--method", "GET", "repos/acme/widgets/pulls/48"],
        [
            "api", "--hostname", "enterprise.internal", "--method", "POST",
            "repos/acme/widgets/issues/48/comments", "--input", "-",
        ],
    ]
    assert json.loads(_calls(cli)[1]["stdin"]) == {"body": FORMATTED}
    assert cli["body"].read_bytes() == BODY.encode("utf-8")


@pytest.mark.parametrize(
    "selector",
    [(), ("--comment-id", "123", "--top-level"), ("--comment-id", "0")],
)
def test_selector_errors_exit_two_before_calling_gh(cli, selector):
    process = _raw_run(
        cli,
        ["--repo", "acme/widgets", "--pr", "48", *selector, "--body-file", str(cli["body"])],
    )
    assert process.returncode == 2
    assert process.stdout == ""
    assert _calls(cli) == []


@pytest.mark.parametrize(
    "pull,code",
    [
        ({"number": 49, "issue_url": "https://enterprise/api/v3/repos/acme/widgets/issues/48"}, "wrong_pr"),
        ({"number": 48, "issue_url": ""}, "wrong_pull_resource"),
    ],
)
def test_top_level_bad_preflight_never_posts(cli, pull, code):
    result_steps = _top_level_steps()
    result_steps[0]["json"] = pull
    status, result = _run(cli, result_steps, selector=("--top-level",))
    assert (status, result["outcome"], result["error"]["code"]) == (1, "not_attempted", code)
    assert len(_calls(cli)) == 1


@pytest.mark.parametrize(
    "patch",
    [
        {"issue_url": "https://wrong.invalid/issues/48"},
        {
            "issue_url": None, "in_reply_to_id": 123,
            "pull_request_url": "https://api.github.com/repos/acme/widgets/pulls/48",
        },
    ],
)
def test_top_level_bad_receipt_is_uncertain_without_retry(cli, patch):
    steps = _top_level_steps()
    steps[1]["json"].update(patch)
    code, result = _run(cli, steps, selector=("--top-level",))
    assert (code, result["outcome"], result["error"]["code"]) == (1, "uncertain", "invalid_receipt")
    assert len(_calls(cli)) == 2
    assert sum("POST" in call["argv"] for call in _calls(cli)) == 1
    assert "Inspect PR comments" in result["error"]["repair"]


@pytest.mark.parametrize("malformed", [False, True])
def test_top_level_post_failures_are_uncertain_without_retry(cli, malformed):
    steps = _top_level_steps()
    steps[1] = {
        "stdout": "{not-json" if malformed else "failure",
        "returncode": 0 if malformed else 1,
    }
    code, result = _run(cli, steps, selector=("--top-level",))
    assert (code, result["outcome"]) == (1, "uncertain")
    assert len(_calls(cli)) == 2
    assert sum("POST" in call["argv"] for call in _calls(cli)) == 1


@pytest.mark.parametrize(
    "step,patch,error,read_count",
    [
        (0, {"id": 999}, "wrong_comment", 1),
        (0, {"in_reply_to_id": 9}, "not_root", 1),
        (1, {"number": 49}, "wrong_pr", 2),
        (0, {"pull_request_url": "https://untrusted.invalid/never-follow"}, "wrong_pull_resource", 2),
        (1, {"url": ""}, "wrong_pull_resource", 2),
    ],
)
def test_bad_preflight_never_posts_or_follows_urls(cli, step, patch, error, read_count):
    steps = _steps()
    steps[step]["json"].update(patch)
    code, result = _run(cli, steps, hostname="enterprise.internal")
    assert (code, result["outcome"], result["error"]["code"]) == (1, "not_attempted", error)
    calls = _calls(cli)
    assert len(calls) == read_count
    assert all(call["argv"][3:5] == ["--method", "GET"] for call in calls)
    assert all(call["argv"][1:3] == ["--hostname", "enterprise.internal"] for call in calls)


def test_boolean_ids_are_not_database_ids(cli):
    steps = _steps()
    steps[0]["json"]["id"] = True
    code, result = _run(cli, steps, extra=["--comment-id", "1"])
    assert (code, result["outcome"], result["error"]["code"]) == (1, "not_attempted", "wrong_comment")
    assert len(_calls(cli)) == 1


@pytest.mark.parametrize("bad_body", [None, b"\xff", b" \r\n\t"])
def test_missing_non_utf8_and_blank_files_never_call_gh(cli, bad_body):
    if bad_body is None:
        cli["body"].unlink()
    else:
        cli["body"].write_bytes(bad_body)
    code, result = _run(cli)
    assert (code, result["outcome"], result["error"]["code"]) == (1, "not_attempted", "invalid_input")
    assert _calls(cli) == []


def test_missing_binary_is_not_attempted(cli):
    (Path(cli["env"]["PATH"]) / "gh").unlink()
    code, result = _run(cli)
    assert (code, result["outcome"], result["error"]["code"]) == (1, "not_attempted", "gh_launch_failed")
    assert _calls(cli) == []


@pytest.mark.parametrize("phase,malformed", [(0, False), (0, True), (2, False), (2, True)])
def test_command_failure_classification_and_diagnostics_without_retries(cli, phase, malformed):
    steps = _steps()
    steps[phase] = {
        "stdout": "{not-json" if malformed else "useful command output",
        "stderr": "diagnostic from selected host",
        "returncode": 0 if malformed else 22,
    }
    code, result = _run(cli, steps, hostname="git.internal", gh_host="do-not-use.internal")
    assert code == 1
    assert result["outcome"] == ("uncertain" if phase == 2 else "not_attempted")
    assert result["error"]["returncode"] == (0 if malformed else 22)
    assert result["error"]["stdout"] == ("{not-json" if malformed else "useful command output")
    assert result["error"]["stderr"] == "diagnostic from selected host"
    calls = _calls(cli)
    assert len(calls) == phase + 1
    assert all(call["argv"][1:3] == ["--hostname", "git.internal"] for call in calls)
    if phase == 2:
        assert "Inspect the thread" in result["error"]["repair"]
        assert sum("POST" in call["argv"] for call in calls) == 1


@pytest.mark.parametrize("patch", [{"in_reply_to_id": 999}, {"body": "rewritten by server"}])
def test_mismatched_receipt_is_uncertain_and_keeps_diagnostics(cli, patch):
    steps = _steps()
    steps[2]["json"].update(patch)
    steps[2]["stderr"] = "receipt warning"
    if "body" in patch:
        steps[2]["echo_body"] = False
    code, result = _run(cli, steps)
    assert (code, result["outcome"], result["error"]["code"]) == (1, "uncertain", "invalid_receipt")
    assert result["error"]["returncode"] == 0
    assert result["error"]["stderr"] == "receipt warning"
    assert json.loads(result["error"]["stdout"])["id"] == 456
    assert BODY not in result["error"]["stdout"]
    assert len(_calls(cli)) == 3
    assert "Inspect the thread" in result["error"]["repair"]


@pytest.mark.parametrize(
    "failure_call,failure,expected",
    [(1, "timeout", "not_attempted"), (3, "timeout", "uncertain"), (3, "missing", "not_attempted")],
)
def test_process_failure_classification_uses_actual_mutation_phase(
    cli, helper, monkeypatch, capsys, failure_call, failure, expected,
):
    calls = []

    class Process:
        returncode = 0

        def __init__(self, argv, **kwargs):
            self.index = len(calls)
            calls.append(argv)
            if self.index + 1 == failure_call and failure == "missing":
                raise FileNotFoundError("gh disappeared before launch")
            self.killed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def communicate(self, payload=None, timeout=None):
            if self.index + 1 == failure_call:
                if not self.killed:
                    raise subprocess.TimeoutExpired(calls[-1], timeout, b"partial out", b"partial err")
                return b"partial out", b"partial err"
            return json.dumps(_steps()[self.index]["json"]).encode(), b""

        def kill(self):
            self.killed = True
            self.returncode = -9

    monkeypatch.setattr(helper.subprocess, "Popen", Process)
    code = helper.main([
        "--hostname", "git.internal", "--repo", "acme/widgets", "--pr", "48",
        "--comment-id", "123", "--body-file", str(cli["body"]),
    ])
    result = json.loads(capsys.readouterr().out)
    assert (code, result["outcome"], result["error"]["code"]) == (
        1, expected, "gh_timeout" if failure == "timeout" else "gh_launch_failed",
    )
    if failure == "timeout":
        assert (result["error"]["stdout"], result["error"]["stderr"]) == ("partial out", "partial err")
    assert len(calls) == failure_call
    assert sum("POST" in argv for argv in calls) == (1 if failure_call == 3 else 0)
    assert all(argv[2:4] == ["--hostname", "git.internal"] for argv in calls)

"""The public offline viewer CLI, persistence, lifecycle, and HTTP boundaries."""

from __future__ import annotations

import concurrent.futures
import hashlib
import http.client
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_VIEWER = ROOT / "src/plugins/nstack/hooks/viewer"
VIEWER = Path(os.environ.get("NSTACK_VIEWER_OUTPUT_DIR", SOURCE_VIEWER))
SAMPLE = SOURCE_VIEWER / "all-components.mdx"
TOOL = ROOT / "tools/visual-viewer"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="Viewer requires Node >=20.")


def cli(entry, env, *args, ok=True):
    proc = subprocess.run([NODE, str(entry), *map(str, args)], env=env, capture_output=True, text=True, timeout=12)
    data = json.loads(proc.stdout)
    assert (proc.returncode == 0) is ok, proc.stdout + proc.stderr
    assert data["ok"] is ok
    return data


@pytest.fixture
def runtime(tmp_path):
    state = tmp_path / "private state"
    env = {**os.environ, "NSTACK_HOME": str(state), "NSTACK_VIEWER": "off"}
    entry = VIEWER / "viewer.mjs"
    yield entry, env, state / "viewer"
    record = state / "viewer/runtime/ready.json"
    if record.exists():
        result = cli(entry, env, "stop")
        assert result["stopped"] is True
        assert not record.exists()


def request(url, path, *, method="GET", data=None, headers=None):
    payload = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(url + path, data=payload, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            raw = response.read()
            body = json.loads(raw) if response.headers.get_content_type() == "application/json" else raw.decode()
            return response.status, body, response.headers
    except urllib.error.HTTPError as error:
        raw = error.read()
        body = json.loads(raw) if error.headers.get_content_type() == "application/json" else raw.decode()
        return error.code, body, error.headers


def mutation_headers(url, token):
    return {"Origin": url, "X-Nstack-Token": token, "Content-Type": "application/json"}


def question_source(prompt="Choose a lifetime?", options=None):
    payload = {"prompt": prompt}
    if options:
        payload["options"] = options
    return (
        '<Document id="feedback-test" kind="plan" title="Feedback">\n\n'
        '<Question id="ttl" title="Lifetime" status="proposed">\n'
        "```json\n" + json.dumps(payload) + "\n```\n</Question>\n\n</Document>\n"
    )


def test_compiler_nonexecution_units():
    proc = subprocess.run(
        [NODE, "--test", str(ROOT / "tests/test_nstack_viewer_compiler.mjs")],
        capture_output=True, text=True, timeout=20,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_browser_dom_units():
    if not (TOOL / "node_modules/linkedom").is_dir():
        pytest.skip("DOM units require npm --prefix tools/visual-viewer ci --ignore-scripts.")
    proc = subprocess.run(
        [NODE, "--test", str(ROOT / "tests/test_nstack_viewer_browser.mjs")],
        capture_output=True, text=True, timeout=20,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_all_components_and_generated_registry(runtime):
    entry, env, state = runtime
    before = sorted(VIEWER.rglob("*"))
    doc = cli(entry, env, "check", SAMPLE)
    reference = cli(entry, env, "components")
    assert reference == json.loads((VIEWER / "components.json").read_text())
    assert set(reference["components"]) == {
        "Diagram", "AnnotatedCode", "FileMap", "BeforeAfter", "Decision",
        "Question", "Wireframe", "StateSequence", "ApiContract", "ApiComparison",
    }
    assert {block["name"] for block in doc["document"]["blocks"] if block["type"] == "component"} == set(reference["components"])
    assert not state.exists(), "check/components must not start a daemon or write state"
    assert sorted(VIEWER.rglob("*")) == before
    bad = cli(entry, env, "check", "relative.mdx", ok=False)
    assert bad["errors"][0]["code"] == "absolute_path_required"


def test_concurrent_ensure_reuses_one_owner_and_verified_stop(runtime):
    entry, env, state = runtime
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(lambda _: cli(entry, env, "ensure"), range(6)))
    assert len({(value["pid"], value["url"], value["buildId"]) for value in results}) == 1
    assert (state.stat().st_mode & 0o077) == 0
    assert cli(entry, env, "ensure")["pid"] == results[0]["pid"]
    assert cli(entry, env, "stop") == {"ok": True, "stopped": True}
    assert not (state / "runtime").exists()
    assert cli(entry, env, "stop") == {"ok": True, "stopped": False}


def test_dead_claim_and_crash_before_record_recover(runtime):
    entry, env, state = runtime
    claim = state / "runtime"
    claim.mkdir(parents=True, mode=0o700)
    os.chmod(state, 0o700)
    dead = subprocess.run([NODE, "-e", "process.stdout.write(String(process.pid))"], capture_output=True, text=True, check=True)
    (claim / "owner.json").write_text(json.dumps({"pid": int(dead.stdout), "nonce": "a" * 48}))
    (claim / "reaper-0.json").write_text(json.dumps({"pid": int(dead.stdout)}))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: cli(entry, env, "ensure"), range(4)))
    assert len({value["pid"] for value in results}) == 1
    assert results[0]["pid"] != int(dead.stdout)
    cli(entry, env, "stop")
    claim.mkdir()
    os.utime(claim, (time.time() - 5, time.time() - 5))
    assert cli(entry, env, "ensure")["ok"]


def test_live_unresponsive_owner_fails_without_signalling(runtime):
    entry, env, state = runtime
    claim = state / "runtime"
    claim.mkdir(parents=True, mode=0o700)
    os.chmod(state, 0o700)
    original = {"pid": os.getpid(), "nonce": "b" * 48}
    (claim / "owner.json").write_text(json.dumps(original))
    result = cli(entry, env, "ensure", ok=False)
    assert result["errors"][0]["code"] == "startup_timeout"
    assert json.loads((claim / "owner.json").read_text()) == original
    assert cli(entry, env, "stop", ok=False)["errors"][0]["code"] == "unverified_owner"
    shutil.rmtree(claim)


@pytest.mark.parametrize("partial", [False, True])
def test_orphan_initializer_temp_is_recovered(runtime, partial):
    entry, env, state = runtime
    claim = state / "runtime"
    claim.mkdir(parents=True, mode=0o700)
    os.chmod(state, 0o700)
    dead = subprocess.run([NODE, "-e", "process.stdout.write(String(process.pid))"], capture_output=True, text=True, check=True)
    original = {"pid": int(dead.stdout), "nonce": "a" * 48}
    orphan = claim / f"owner.json.{dead.stdout}.{'c' * 48}.tmp"
    orphan.write_text('{"pid":' if partial else json.dumps(original))
    os.utime(claim, (time.time() - 5, time.time() - 5))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: cli(entry, env, "ensure"), range(4)))
    assert len({value["pid"] for value in results}) == 1
    assert not orphan.exists()


@pytest.mark.parametrize("location", ["owner", "initializer"])
def test_previous_boot_claim_with_reused_live_pid_recovers_without_signalling(runtime, tmp_path, location):
    entry, env, state = runtime
    claim = state / "runtime"
    claim.mkdir(parents=True, mode=0o700)
    os.chmod(state, 0o700)
    original = {"pid": os.getpid(), "nonce": "b" * 48, "bootId": "previous-boot"}
    record_name = "owner.json" if location == "owner" else f"owner.json.{os.getpid()}.{'c' * 48}.tmp"
    (claim / record_name).write_text(json.dumps(original))
    os.utime(claim, (time.time() - 5, time.time() - 5))
    log = tmp_path / "signals.jsonl"
    preload = tmp_path / "signal-audit.cjs"
    preload.write_text(
        "const fs = require('node:fs'); const original = process.kill;\n"
        "process.kill = (pid, signal) => {\n"
        "  fs.appendFileSync(process.env.NSTACK_SIGNAL_LOG, JSON.stringify({pid,signal}) + '\\n');\n"
        "  if (signal !== 0) throw new Error('A recovery operation attempted to send a signal');\n"
        "  return original(pid, signal);\n"
        "};\n"
    )
    result = cli(entry, {**env, "NODE_OPTIONS": f'--require="{preload}"', "NSTACK_SIGNAL_LOG": str(log)}, "ensure")
    assert result["pid"] != os.getpid()
    assert json.loads((claim / "owner.json").read_text())["bootId"] != "previous-boot"
    probes = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    assert all(probe["signal"] == 0 for probe in probes)
    assert all(probe["pid"] != os.getpid() for probe in probes)
    os.kill(os.getpid(), 0)


@pytest.mark.parametrize("contents", ["foreign", "live_initializer"])
def test_uninitialized_claim_preserves_unknown_files_and_live_writers(runtime, contents):
    entry, env, state = runtime
    claim = state / "runtime"
    claim.mkdir(parents=True, mode=0o700)
    os.chmod(state, 0o700)
    file = claim / ("foreign.txt" if contents == "foreign" else f"owner.json.{os.getpid()}.{'a' * 48}.tmp")
    file.write_text("preserve this partial initialization")
    os.utime(claim, (time.time() - 5, time.time() - 5))
    assert cli(entry, env, "ensure", ok=False)["errors"][0]["code"] == "startup_timeout"
    assert file.read_text() == "preserve this partial initialization"
    assert sorted(claim.iterdir()) == [file]
    shutil.rmtree(claim)


def test_claim_disappearing_during_recovery_is_retried(runtime, tmp_path):
    entry, env, state = runtime
    claim = state / "runtime"
    claim.mkdir(parents=True, mode=0o700)
    os.chmod(state, 0o700)
    os.utime(claim, (time.time() - 5, time.time() - 5))
    preload = tmp_path / "cleanup-race.cjs"
    preload.write_text(
        "const fs = require('node:fs'); const original = fs.statSync;\n"
        "fs.statSync = (file, ...args) => {\n"
        "  if (file === process.env.NSTACK_RACE_CLAIM && fs.existsSync(file)) fs.rmSync(file, {recursive:true});\n"
        "  return original(file, ...args);\n"
        "}; require('node:module').syncBuiltinESMExports();\n"
    )
    raced = {**env, "NODE_OPTIONS": f'--require="{preload}"', "NSTACK_RACE_CLAIM": str(claim)}
    result = cli(entry, raced, "ensure")
    assert result["pid"] == json.loads((claim / "owner.json").read_text())["pid"]
    assert cli(entry, env, "ensure")["pid"] == result["pid"]


def test_concurrent_startup_during_verified_cleanup_retains_one_ready_owner(runtime):
    entry, env, state = runtime
    for _ in range(5):
        first = cli(entry, env, "ensure")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            stopping = executor.submit(cli, entry, env, "stop")
            starting = [executor.submit(cli, entry, env, "ensure") for _ in range(4)]
            assert stopping.result() == {"ok": True, "stopped": True}
            results = [future.result() for future in starting]
        final = cli(entry, env, "ensure")
        assert {value["pid"] for value in results}.issubset({first["pid"], final["pid"]})
        assert json.loads((state / "runtime/owner.json").read_text())["pid"] == final["pid"]
        assert request(final["url"], "/health?nonce=" + json.loads((state / "runtime/ready.json").read_text())["nonce"])[0] == 200


def test_detached_server_does_not_retain_credentials_or_node_injection_environment(runtime):
    entry, env, state = runtime
    sentinel = "nstack-fake-secret-never-retain-924c"
    result = cli(entry, {**env, "NSTACK_FAKE_SECRET": sentinel, "NODE_OPTIONS": "--no-warnings", "NODE_PATH": sentinel}, "ensure")
    if sys.platform == "darwin":
        environment = subprocess.run(["/bin/ps", "eww", "-p", str(result["pid"]), "-o", "command="], capture_output=True, text=True, check=True).stdout
    else:
        environment = Path(f"/proc/{result['pid']}/environ").read_bytes().decode().replace("\0", "\n")
    assert "NSTACK_HOME=" in environment
    assert str(state.parent) in environment
    assert sentinel not in environment
    assert "NSTACK_FAKE_SECRET=" not in environment
    assert "NODE_OPTIONS=" not in environment and "NODE_PATH=" not in environment


def test_native_windows_is_rejected_before_state_permissions_are_used(runtime):
    entry, env, state = runtime
    proc = subprocess.run(
        [NODE, "--import", "data:text/javascript,Object.defineProperty(process,'platform',{value:'win32'})", str(entry), "ensure"],
        env=env, capture_output=True, text=True, timeout=5,
    )
    assert proc.returncode == 1
    failure = json.loads(proc.stdout)["errors"][0]
    assert failure["code"] == "unsupported_platform"
    assert "WSL, Linux, or macOS" in failure["repair"]
    assert not state.exists()


def test_symlinked_cli_entry_in_path_with_spaces(runtime, tmp_path):
    entry, env, _ = runtime
    link = tmp_path / "installed with spaces" / "viewer link.mjs"
    link.parent.mkdir()
    link.symlink_to(entry)
    assert cli(link, env, "components")["version"] == 1


def test_private_browser_capability_bootstrap_and_authenticated_boundaries(runtime, tmp_path):
    entry, env, state = runtime
    path = tmp_path / "private.mdx"
    path.write_text(question_source())
    opened = cli(entry, env, "open", path)
    parsed = urlsplit(opened["url"])
    origin = f"{parsed.scheme}://{parsed.netloc}"
    record = json.loads((state / "runtime/ready.json").read_text())
    for route in ["/api/session", "/api/documents", "/api/documents/feedback-test", "/api/answers/feedback-test"]:
        status, body, _ = request(origin, route)
        assert status == 403, route
        assert body["errors"][0]["code"] == "access_required"
        assert record["token"] not in json.dumps(body)
    status, page, _ = request(origin, "/documents/feedback-test")
    assert status == 403
    assert "open" in page and "URL" in page
    for route in ["/api/publish", "/api/answers/feedback-test/ttl", "/api/stop"]:
        assert request(origin, route, method="POST", data={}, headers={"Origin": origin, "Content-Type": "application/json"})[0] == 403
    assert parsed.query, "open.url must carry a private capability"
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=3)
    conn.request("GET", parsed.path + "?" + parsed.query)
    response = conn.getresponse()
    assert response.status == 303
    assert response.headers["Location"] == "/documents/feedback-test"
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Path=/" in cookie
    assert "Domain=" not in cookie and "Expires=" not in cookie and "Max-Age=" not in cookie
    assert record["token"] not in response.read().decode()
    conn.close()
    assert request(origin, parsed.path + "?capability=invalid")[0] == 403
    assert request(origin, parsed.path + "?" + parsed.query, headers={"Origin": "http://foreign.invalid"})[0] == 403
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=3)
    conn.request("GET", "/?" + parsed.query)
    response = conn.getresponse()
    assert response.status == 303 and response.headers["Location"] == "/"
    response.read()
    conn.close()
    browser_headers = {"Cookie": cookie.split(";")[0]}
    assert request(origin, "/documents/feedback-test", headers=browser_headers)[0] == 200
    session = request(origin, "/api/session", headers=browser_headers)[1]
    assert session == {"ok": True, "buildId": record["buildId"]}
    document = request(origin, "/api/documents/feedback-test", headers=browser_headers)[1]
    answer = {"value": "Browser feedback", "digest": document["blocks"][0]["questionDigest"]}
    status, saved, _ = request(origin, "/api/answers/feedback-test/ttl", method="POST", data=answer, headers={**browser_headers, "Origin": origin, "Content-Type": "application/json"})
    assert status == 200 and saved["answers"][0]["value"] == "Browser feedback"
    assert cli(entry, env, "answers", "feedback-test")["answers"][0]["value"] == "Browser feedback"
    readiness = request(origin, f"/health?nonce={record['nonce']}")[1]
    assert readiness == {key: record[key] for key in ["protocol", "nonce", "buildId", "pid", "rootHash"]}
    for credentials in [browser_headers, {"X-Nstack-Token": record["token"]}]:
        for route in ["/api/session", "/api/documents/feedback-test", "/api/answers/feedback-test"]:
            assert request(origin, route, headers={**credentials, "Origin": "http://foreign.invalid"})[0] == 403
            assert request(origin, route, headers={**credentials, "Host": f"localhost:{parsed.port}"})[0] == 403
        assert request(origin, "/api/stop", method="POST", data={}, headers={**credentials, "Origin": "http://foreign.invalid", "Content-Type": "application/json"})[0] == 403
        assert request(origin, "/api/stop", method="POST", data={}, headers={**credentials, "Host": f"localhost:{parsed.port}", "Origin": origin, "Content-Type": "application/json"})[0] == 403


@pytest.mark.parametrize("choice", ["x", "x" * 10000, "😀" * 5000], ids=["one-unit", "max-ascii", "max-surrogate-pairs"])
def test_published_choice_boundaries_persist_through_public_answer_api(runtime, tmp_path, choice):
    entry, env, state = runtime
    path = tmp_path / "choices.mdx"
    path.write_text(question_source(options=["Other", choice]))
    opened = cli(entry, env, "open", path)
    origin = opened["url"].split("/documents/")[0]
    token = json.loads((state / "runtime/ready.json").read_text())["token"]
    question = request(origin, "/api/documents/feedback-test", headers={"X-Nstack-Token": token})[1]["blocks"][0]
    status, saved, _ = request(origin, "/api/answers/feedback-test/ttl", method="POST", data={"value": choice, "digest": question["questionDigest"]}, headers=mutation_headers(origin, token))
    assert status == 200 and saved["answers"][0]["value"] == choice
    cli(entry, env, "stop")
    assert cli(entry, env, "answers", "feedback-test")["answers"][0]["value"] == choice
    assert not (state / "runtime").exists()


def test_free_text_answers_keep_nonblank_and_length_constraints(runtime, tmp_path):
    entry, env, state = runtime
    path = tmp_path / "text.mdx"
    path.write_text(question_source())
    opened = cli(entry, env, "open", path)
    origin = opened["url"].split("/documents/")[0]
    token = json.loads((state / "runtime/ready.json").read_text())["token"]
    question = request(origin, "/api/documents/feedback-test", headers={"X-Nstack-Token": token})[1]["blocks"][0]
    for value in [" \t\n", "x" * 10001]:
        status, body, _ = request(origin, "/api/answers/feedback-test/ttl", method="POST", data={"value": value, "digest": question["questionDigest"]}, headers=mutation_headers(origin, token))
        assert status == 400 and body["errors"][0]["code"] == "invalid_answer"
    value = " " + "x" * 9998 + " "
    assert request(origin, "/api/answers/feedback-test/ttl", method="POST", data={"value": value, "digest": question["questionDigest"]}, headers=mutation_headers(origin, token))[0] == 200
    assert cli(entry, env, "answers", "feedback-test")["answers"][0]["value"] == value


def test_answers_do_not_start_daemon_or_depend_on_build_readiness(runtime, tmp_path):
    entry, env, state = runtime
    path = tmp_path / "feedback.mdx"
    path.write_text(question_source())
    opened = cli(entry, env, "open", path)
    origin = opened["url"].split("/documents/")[0]
    token = json.loads((state / "runtime/ready.json").read_text())["token"]
    document = request(origin, "/api/documents/feedback-test", headers={"X-Nstack-Token": token})[1]
    status, _, _ = request(origin, "/api/answers/feedback-test/ttl", method="POST", data={"value": "Retained", "digest": document["blocks"][0]["questionDigest"]}, headers=mutation_headers(origin, token))
    assert status == 200
    cli(entry, env, "stop")
    preload = tmp_path / "no-child-processes.cjs"
    preload.write_text(
        "const child = require('node:child_process');\n"
        "for (const name of ['spawn','spawnSync','exec','execSync','execFile','execFileSync','fork']) {\n"
        "  child[name] = () => { throw new Error('Read-only answers must not start child processes'); };\n"
        "}\n"
        "require('node:module').syncBuiltinESMExports();\n"
    )
    readonly = {**env, "NODE_OPTIONS": f'--require="{preload}"'}
    assert cli(entry, readonly, "answers", "feedback-test")["answers"][0]["value"] == "Retained"
    assert not (state / "runtime").exists(), "answers must not spawn a viewer"
    cli(entry, env, "ensure")
    record_path = state / "runtime/ready.json"
    original = record_path.read_text()
    mismatched = json.loads(original)
    mismatched["buildId"] = "intentionally-mismatched"
    record_path.write_text(json.dumps(mismatched))
    try:
        assert cli(entry, readonly, "answers", "feedback-test")["answers"][0]["value"] == "Retained"
        assert json.loads(record_path.read_text()) == mismatched
    finally:
        record_path.write_text(original)


def test_answers_preserve_valid_v1_feedback_when_current_publication_rules_are_stricter(runtime, tmp_path):
    entry, env, state = runtime
    path = tmp_path / "original-canonical.mdx"
    path.write_text(question_source(options=["Valid choice", "Other choice"]))
    document = cli(entry, env, "check", path)["document"]
    source = question_source(options=["Valid choice", " "])
    options = ["Valid choice", " "]
    question_digest = hashlib.sha256(json.dumps(["Choose a lifetime?", options], separators=(",", ":")).encode()).hexdigest()
    document["revision"] = hashlib.sha256(source.encode()).hexdigest()
    document["blocks"][0]["data"]["options"] = options
    document["blocks"][0]["questionDigest"] = question_digest
    (state / "documents").mkdir(parents=True, mode=0o700)
    (state / "answers").mkdir(mode=0o700)
    (state / "documents/feedback-test.json").write_text(json.dumps({
        "sourcePath": str(path.resolve()), "source": source, "publishedAt": "2026-01-01T00:00:00Z", "document": document,
    }))
    (state / "answers/feedback-test.json").write_text(json.dumps({
        "ttl": {"value": "Valid choice", "digest": question_digest, "savedAt": "2026-01-01T00:00:00Z"},
    }))
    path.unlink()
    assert cli(entry, env, "answers", "feedback-test") == {
        "ok": True, "docId": "feedback-test", "revision": document["revision"],
        "answers": [{"blockId": "ttl", "value": "Valid choice", "digest": question_digest, "savedAt": "2026-01-01T00:00:00Z", "stale": False, "active": True, "removed": False}],
    }
    assert not (state / "runtime").exists()
    answer_file = state / "answers/feedback-test.json"
    answer_file.write_text('{"ttl":{"value":42}}')
    assert cli(entry, env, "answers", "feedback-test", ok=False)["errors"][0]["code"] == "corrupt_state"
    assert not (state / "runtime").exists()


def test_answers_survive_restart_and_become_stale_without_mixing_sources(runtime, tmp_path):
    entry, env, state = runtime
    path = tmp_path / "feedback.mdx"
    path.write_text(question_source(options=["15 minutes", "1 hour"]))
    opened = cli(entry, env, "open", path)
    url = opened["url"].split("/documents/")[0]
    token = json.loads((state / "runtime/ready.json").read_text())["token"]
    doc = request(url, "/api/documents/feedback-test", headers={"X-Nstack-Token": token})[1]
    question = doc["blocks"][0]
    headers = mutation_headers(url, token)
    status, answer, _ = request(url, "/api/answers/feedback-test/ttl", method="POST", data={"value": "15 minutes", "digest": question["questionDigest"]}, headers=headers)
    assert status == 200
    assert answer["answers"][0]["value"] == "15 minutes"
    assert answer["answers"][0]["active"] is True
    cli(entry, env, "stop")
    reloaded = cli(entry, env, "answers", "feedback-test")
    assert reloaded["answers"][0]["value"] == "15 minutes"
    assert reloaded["answers"][0]["stale"] is False
    path.write_text(question_source("Choose another lifetime?", ["30 minutes", "2 hours"]))
    changed = cli(entry, env, "open", path)
    stale = cli(entry, env, "answers", "feedback-test")["answers"][0]
    assert stale["stale"] is True and stale["active"] is False
    assert stale["value"] == "15 minutes"
    current_url = changed["url"].split("/documents/")[0]
    current_token = json.loads((state / "runtime/ready.json").read_text())["token"]
    stale_status, stale_error, _ = request(current_url, "/api/answers/feedback-test/ttl", method="POST", data={"value": "15 minutes", "digest": question["questionDigest"]}, headers=mutation_headers(current_url, current_token))
    assert stale_status == 409
    assert stale_error["errors"][0]["code"] == "stale_question"
    duplicate = tmp_path / "other.mdx"
    duplicate.write_text(path.read_text())
    conflict = cli(entry, env, "open", duplicate, ok=False)
    assert conflict["errors"][0]["code"] == "source_conflict"
    assert "original canonical MDX source path" in conflict["errors"][0]["repair"]
    assert "migration is not supported" in conflict["errors"][0]["repair"]
    assert json.loads((state / "documents/feedback-test.json").read_text())["sourcePath"] == str(path.resolve())
    path.unlink()
    current = cli(entry, env, "ensure")
    assert request(current["url"], "/api/documents/feedback-test", headers={"X-Nstack-Token": current_token})[1]["title"] == "Feedback"


def test_http_guards_assets_and_no_network_execution(runtime):
    entry, env, state = runtime
    current = cli(entry, env, "ensure")
    url = current["url"]
    token = json.loads((state / "runtime/ready.json").read_text())["token"]
    for headers, code in [
        ({}, "origin_required"),
        ({"Origin": "http://example.com"}, "origin_rejected"),
        ({"Origin": url}, "access_required"),
        ({"Origin": url, "X-Nstack-Token": token, "Content-Type": "text/plain"}, "content_type"),
    ]:
        status, body, _ = request(url, "/api/stop", method="POST", data={}, headers=headers)
        assert status in (403, 415)
        assert body["errors"][0]["code"] == code
        assert body["errors"][0]["repair"]
    port = int(url.rsplit(":", 1)[1])
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    conn.request("GET", "/api/session", headers={"Host": f"localhost:{port}"})
    response = conn.getresponse()
    assert response.status == 403
    assert json.loads(response.read())["errors"][0]["code"] == "host_rejected"
    conn.close()
    for path in ["/assets/../src/cli.mjs", "/api/files/etc/passwd", "/documents/missing", "/assets/secrets.json"]:
        assert request(url, path, headers={"X-Nstack-Token": token})[0] == 404
    status, _, headers = request(url, "/api/session", headers={"X-Nstack-Token": token})
    assert status == 200
    assert "unsafe-eval" not in headers["Content-Security-Policy"]
    assert headers.get("Access-Control-Allow-Origin") is None
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    req = urllib.request.Request(url + "/assets/browser.js")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
    oversized = {"source": "x" * 2_100_001, "sourcePath": "/not-read.mdx"}
    assert request(url, "/api/publish", method="POST", data=oversized, headers=mutation_headers(url, token))[0] == 413
    assert (state / "runtime/ready.json").is_file()
    assert request(url, "/health?nonce=wrong")[0] == 404
    assert request(url, "/api/send", method="POST", data={}, headers=mutation_headers(url, token))[0] == 404


@pytest.mark.parametrize("layout", ["hooks", "com.github.copilot/hooks", "codex/hooks"])
def test_copied_offline_install_has_no_runtime_dependencies_or_writes(runtime, tmp_path, layout):
    _, env, _ = runtime
    hooks = tmp_path / "installed read only" / layout / "viewer"
    shutil.copytree(VIEWER, hooks)
    shutil.copyfile(SAMPLE, hooks / "all-components.mdx")
    before = {str(path.relative_to(hooks)): path.read_bytes() for path in hooks.rglob("*") if path.is_file()}
    result = cli(hooks / "viewer.mjs", env, "open", hooks / "all-components.mdx")
    assert result["docId"] == "nstack-components-reference"
    after = {str(path.relative_to(hooks)): path.read_bytes() for path in hooks.rglob("*") if path.is_file()}
    assert before == after
    assert not list(hooks.rglob("node_modules"))


def test_manifest_hashes_and_reproducible_rebuild(tmp_path):
    manifest = json.loads((VIEWER / "manifest.json").read_text())
    for path, expected in manifest["inputs"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
    for path, expected in manifest["outputs"].items():
        assert hashlib.sha256((VIEWER / path).read_bytes()).hexdigest() == expected, path
    assert (VIEWER / "THIRD-PARTY-NOTICES").read_text().count("MIT") > 10
    if not (TOOL / "node_modules/esbuild").is_dir():
        pytest.skip("Rebuild requires npm --prefix tools/visual-viewer ci --ignore-scripts.")
    proc = subprocess.run(["npm", "--prefix", str(TOOL), "run", "check"], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    other_cwd = subprocess.run([NODE, str(TOOL / "build.mjs"), "--check"], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert other_cwd.returncode == 0, other_cwd.stdout + other_cwd.stderr

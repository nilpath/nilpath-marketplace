"""The public offline viewer CLI, persistence, lifecycle, and HTTP boundaries."""

from __future__ import annotations

import concurrent.futures
import hashlib
import http.client
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "src/plugins/nstack/hooks/viewer"
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
            return response.status, json.loads(raw), response.headers
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read()), error.headers


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
    doc = cli(entry, env, "check", VIEWER / "all-components.mdx")
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


def test_answers_survive_restart_and_become_stale_without_mixing_sources(runtime, tmp_path):
    entry, env, state = runtime
    path = tmp_path / "feedback.mdx"
    path.write_text(question_source(options=["15 minutes", "1 hour"]))
    opened = cli(entry, env, "open", path)
    url = opened["url"].split("/documents/")[0]
    session = request(url, "/api/session")[1]
    doc = request(url, "/api/documents/feedback-test")[1]
    question = doc["blocks"][0]
    headers = mutation_headers(url, session["token"])
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
    current_session = request(current_url, "/api/session")[1]
    stale_status, stale_error, _ = request(current_url, "/api/answers/feedback-test/ttl", method="POST", data={"value": "15 minutes", "digest": question["questionDigest"]}, headers=mutation_headers(current_url, current_session["token"]))
    assert stale_status == 409
    assert stale_error["errors"][0]["code"] == "stale_question"
    duplicate = tmp_path / "other.mdx"
    duplicate.write_text(path.read_text())
    conflict = cli(entry, env, "open", duplicate, ok=False)
    assert conflict["errors"][0]["code"] == "source_conflict"
    assert json.loads((state / "documents/feedback-test.json").read_text())["sourcePath"] == str(path.resolve())
    path.unlink()
    current = cli(entry, env, "ensure")
    assert request(current["url"], "/api/documents/feedback-test")[1]["title"] == "Feedback"


def test_http_guards_assets_and_no_network_execution(runtime):
    entry, env, state = runtime
    current = cli(entry, env, "ensure")
    url = current["url"]
    session = request(url, "/api/session")[1]
    token = session["token"]
    for headers, code in [
        ({}, "origin_required"),
        ({"Origin": "http://example.com"}, "origin_rejected"),
        ({"Origin": url}, "token_rejected"),
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
        assert request(url, path)[0] == 404
    status, _, headers = request(url, "/api/session")
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

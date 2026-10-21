"""Probe real CLI permissions with disposable fixtures and loopback model stubs.

Run with --output-dir outside the checkout. No credentials, inherited settings,
allow-all flags, or real project content enter the fixture sessions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import pty
import select
import shutil
import struct
import subprocess
import tempfile
import termios
import threading
import time


@dataclass(frozen=True)
class Case:
    name: str
    rule: str | None
    command: str = '"@SKILL@/helper.sh"'
    path_access: bool = True
    deny: bool = False
    second_turn: bool = False
    cwd: str = "workspace"


DIRECT = '"@ROOT@/skills/permission-fixture/helper.sh":*'
PYTHON = 'python3 "@ROOT@/skills/permission-fixture/helper.py":*'
CASES = (
    Case("baseline", None),
    Case("direct", DIRECT),
    Case("direct-arguments", DIRECT, '"@SKILL@/helper.sh" "argument with spaces"'),
    Case("command-substitution", DIRECT, 'COMMENTS=$("@SKILL@/helper.sh"); printf "%s\\n" "$COMMENTS"'),
    Case("pipeline", DIRECT, 'printf "{}" | "@SKILL@/helper.sh"'),
    Case("other-script", DIRECT, '"@SKILL@/other.sh"'),
    Case("python", PYTHON, 'python3 "@SKILL@/helper.py"'),
    Case("python-arguments", PYTHON, 'python3 "@SKILL@/helper.py" "argument with spaces"'),
    Case("python-other", PYTHON, 'python3 "@SKILL@/other.py"'),
    Case("python-inline", PYTHON, "python3 -c \"print('inline-command')\""),
    Case("direct-not-python", DIRECT, 'python3 "@SKILL@/helper.py"'),
    Case("path-check", DIRECT, path_access=False),
    Case("deny-precedence", DIRECT, deny=True),
    Case("different-cwd", DIRECT, cwd="other workspace"),
    Case("portable-root", DIRECT.replace("@ROOT@", "@VARIABLE@")),
    Case("portable-python", PYTHON.replace("@ROOT@", "@VARIABLE@"), 'python3 "@SKILL@/helper.py"'),
    Case("next-turn", DIRECT, second_turn=True),
    Case("url-check", "curl:*", 'curl --max-time 2 @URL@'),
)


def completion(call: dict | None, stream: bool, call_id: str) -> bytes:
    message = {"role": "assistant", "content": None if call else "Fixture complete."}
    if call:
        message["tool_calls"] = [{"id": call_id, "type": "function", "function": call}]
    payload = {
        "id": "fixture", "object": "chat.completion", "created": 1,
        "model": "permission-fixture",
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if call else "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    if not stream:
        return json.dumps(payload).encode()
    delta = dict(message)
    for index, tool in enumerate(delta.get("tool_calls", [])):
        tool["index"] = index
    payload["object"] = "chat.completion.chunk"
    payload["choices"] = [{"index": 0, "delta": delta, "finish_reason": None}]
    ending = {
        "id": "fixture", "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls" if call else "stop"}],
    }
    return f"data: {json.dumps(payload)}\n\ndata: {json.dumps(ending)}\n\ndata: [DONE]\n\n".encode()


def anthropic(call: dict | None, stream: bool, call_id: str) -> bytes:
    content = {"type": "text", "text": "Fixture complete."}
    if call:
        content = {
            "type": "tool_use", "id": call_id,
            "name": call["name"], "input": json.loads(call["arguments"]),
        }
    payload = {
        "id": "msg_fixture", "type": "message", "role": "assistant",
        "content": [content], "model": "claude-sonnet-4-6",
        "stop_reason": "tool_use" if call else "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    if not stream:
        return json.dumps(payload).encode()
    events = [
        ("message_start", {
            "type": "message_start", "message": {**payload, "content": [], "stop_reason": None},
        }),
        ("content_block_start", {
            "type": "content_block_start", "index": 0,
            "content_block": {**content, **({"input": {}} if call else {"text": ""})},
        }),
        ("content_block_delta", {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": json.dumps(content["input"])}
            if call else {"type": "text_delta", "text": content["text"]},
        }),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {
            "type": "message_delta",
            "delta": {"stop_reason": payload["stop_reason"], "stop_sequence": None},
            "usage": {"output_tokens": 1},
        }),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(f"event: {name}\ndata: {json.dumps(value)}\n\n" for name, value in events).encode()


def tool_results(body: dict, client: str) -> list[dict]:
    if client == "copilot":
        return [m for m in body.get("messages", []) if m.get("role") == "tool"]
    return [
        block for message in body.get("messages", [])
        if isinstance(message.get("content"), list)
        for block in message["content"] if block.get("type") == "tool_result"
    ]


def drive_terminal(
    command: list[str], env: dict[str, str], cwd: Path, state: dict, second_turn: bool
) -> str:
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 160, 0, 0))
    proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=slave, stdout=slave, stderr=slave)
    os.close(slave)
    transcript = b""
    trusted = False
    sent_second = False
    submitted_second = False
    second_input_offset = 0
    try:
        deadline = time.monotonic() + 25
        while proc.poll() is None and time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try:
                    transcript += os.read(master, 65536)
                except OSError:
                    break
            if not trusted and b"Do you trust the files" in transcript and b"1. Yes" in transcript:
                os.write(master, b"\r")
                trusted = True
            if any(prompt in transcript for prompt in (
                b"Do you want to allow", b"Do you want to run this command?", b"Allow tool",
            )):
                break
            second_input = b"Run the same fixture helper again without invoking the skill."
            if sent_second and not submitted_second and second_input in transcript[second_input_offset:]:
                os.write(master, b"\r")
                submitted_second = True
            if state["completed"] and b"Fixture complete." in transcript:
                if second_turn and not sent_second:
                    state["stage"] = "second"
                    state["completed"] = False
                    second_input_offset = len(transcript)
                    os.write(master, second_input)
                    sent_second = True
                elif not second_turn or state["second_completed"]:
                    break
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        os.close(master)
    return transcript.decode(errors="replace")


def drive_claude_turns(
    command: list[str], env: dict[str, str], cwd: Path, state: dict
) -> tuple[str, str, int]:
    command = command[:-2] + ["--input-format", "stream-json", "-p"]
    proc = subprocess.Popen(
        command, cwd=cwd, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    transcript = b""
    pending = b""
    turns = 0
    assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None

    def send(text: str) -> None:
        message = {"type": "user", "message": {"role": "user", "content": text}}
        proc.stdin.write((json.dumps(message) + "\n").encode())
        proc.stdin.flush()

    try:
        send("/permission-fixture:permission-fixture")
        deadline = time.monotonic() + 40
        while proc.poll() is None and time.monotonic() < deadline:
            ready, _, _ = select.select([proc.stdout], [], [], 0.1)
            if not ready:
                continue
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                break
            transcript += chunk
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                event = json.loads(line)
                if event.get("type") != "result":
                    continue
                turns += 1
                if turns == 1:
                    state["stage"] = "second"
                    send("Run the same helper again without invoking the skill.")
                else:
                    proc.stdin.close()
            if turns == 2:
                break
        proc.terminate()
        proc.wait(timeout=3)
        return transcript.decode(), proc.stderr.read().decode(), proc.returncode
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close()


def probe(executable: str, client: str, case: Case, interactive: bool) -> dict:
    with tempfile.TemporaryDirectory(prefix="skill-permission-") as tmp:
        root = Path(tmp).resolve()
        home = root / "home"
        cwd = root / case.cwd
        plugin = root / "installed plugin with spaces"
        skill = plugin / "skills/permission-fixture"
        for directory in (home, cwd, skill):
            directory.mkdir(parents=True)
        manifest = json.dumps({"name": "permission-fixture", "version": "1.0.0"})
        (plugin / ".claude-plugin").mkdir()
        (plugin / ".claude-plugin/plugin.json").write_text(manifest)
        (plugin / "plugin.json").write_text(manifest)
        for name in ("helper", "other"):
            script = skill / f"{name}.sh"
            script.write_text(
                f'#!/bin/sh\nprintf "{name}-executed\\n"\npwd\n'
                f'touch "$(dirname "$0")/{name}.effect"\n'
            )
            script.chmod(0o755)
            (skill / f"{name}.py").write_text(
                "from pathlib import Path\n"
                f"print('{name}-python-executed')\n"
                "print(Path.cwd())\n"
                f"with Path(__file__).with_name('{name}.effect').open('a') as output:\n"
                "    output.write('x')\n"
            )
        variable = "${CLAUDE_PLUGIN_ROOT}"

        def expand(text: str) -> str:
            if "@URL@" in text:
                text = text.replace("@URL@", f"http://127.0.0.1:{server.server_port}/fixture-url")
            return (
                text.replace("@ROOT@", str(plugin))
                .replace("@SKILL@", str(skill)).replace("@VARIABLE@", variable)
            )

        rule = f'{"Bash" if client == "claude" else "shell"}({expand(case.rule)})' if case.rule else None
        instruction_root = variable if case.rule and "@VARIABLE@" in case.rule else str(plugin)
        instruction = f'Run "{instruction_root}/skills/permission-fixture/helper.sh" from the current working directory.'
        resolved_instruction = f'Run "{skill}/helper.sh" from the current working directory.'
        tools_frontmatter = ""
        if rule:
            tools_frontmatter = (
                f"allowed-tools: Read, {rule}\n" if client == "claude"
                else f"allowed-tools:\n  - {json.dumps(rule)}\n"
            )
        (skill / "SKILL.md").write_text(
            "---\nname: permission-fixture\ndescription: Harmless local permission fixture.\n"
            + tools_frontmatter
            + f'---\n{instruction}\n'
        )
        state = {
            "stage": "initial", "completed": False, "second_completed": False,
            "requests": [], "results": [], "url_requests": 0,
            "instruction_path_expanded": False, "instruction_variable_literal": False,
        }

        class Provider(BaseHTTPRequestHandler):
            def log_message(self, *unused):
                pass

            def do_GET(self):
                if self.path != "/fixture-url":
                    self.send_error(404)
                    return
                state["url_requests"] += 1
                data = b"fixture-url-executed"
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                context = str(body.get("messages", []))
                state["instruction_path_expanded"] |= resolved_instruction in context
                if instruction_root == variable:
                    state["instruction_variable_literal"] |= instruction in context
                results = tool_results(body, client)
                state["results"] = results
                if client == "claude" and self.path.endswith("count_tokens"):
                    data = b'{"input_tokens":1}'
                else:
                    count = len(results)
                    call = None
                    if client == "copilot" and count == 0:
                        call = {"name": "skill", "arguments": json.dumps({"skill": "permission-fixture"})}
                    elif count == (1 if client == "copilot" else 0) or state["stage"] == "second":
                        call = {
                            "name": "Bash" if client == "claude" else "bash",
                            "arguments": json.dumps({
                                "command": expand(case.command), "description": "Run harmless fixture",
                            }),
                        }
                        if state["stage"] == "second":
                            state["stage"] = "second-sent"
                    else:
                        state["completed"] = True
                        state["second_completed"] = state["stage"] == "second-sent"
                    state["requests"].append({"path": self.path, "call": call, "results": results})
                    data = (anthropic if client == "claude" else completion)(
                        call, body.get("stream", False), f"fixture_call_{len(state['requests'])}"
                    )
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream" if body.get("stream") else "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        path = os.pathsep.join(dict.fromkeys((
            str(Path(shutil.which("python3")).parent), "/opt/homebrew/bin", os.defpath,
        )))
        env = {"HOME": str(home), "PATH": path, "TERM": "xterm-256color", "NO_COLOR": "1"}
        if client == "copilot":
            env.update({
                "COPILOT_HOME": str(home / ".copilot"), "COPILOT_OFFLINE": "true",
                "COPILOT_PROVIDER_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1",
                "COPILOT_PROVIDER_TYPE": "openai", "COPILOT_PROVIDER_WIRE_API": "completions",
                "COPILOT_MODEL": "permission-fixture",
            })
            command = [
                executable, "--no-auto-update", "--disable-builtin-mcps",
                "--no-custom-instructions", "--no-ask-user", "--plugin-dir", str(plugin),
            ]
            if case.path_access:
                command += ["--add-dir", str(plugin)]
            if case.deny:
                command += ["--deny-tool", f'shell("{skill}/helper.sh":*)']
            if interactive:
                command += ["--screen-reader", "-i", "Invoke the fixture skill, then run its helper."]
            else:
                command += [
                    "--trust-folder", "--stream", "off", "--output-format", "json",
                    "-p", "Invoke the fixture skill, then run its helper.",
                ]
        else:
            env.update({
                "CLAUDE_CONFIG_DIR": str(home / ".claude"),
                "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                "ANTHROPIC_API_KEY": "local-fixture-not-a-secret",
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            })
            command = [
                executable, "--bare", "--setting-sources", "", "--strict-mcp-config",
                "--mcp-config", '{"mcpServers":{}}', "--no-session-persistence",
                "--permission-mode", "manual", "--plugin-dir", str(plugin),
                "--output-format", "stream-json", "--verbose", "--model", "claude-sonnet-4-6",
            ]
            if case.deny:
                command += ["--settings", json.dumps({"permissions": {"deny": [f'Bash("{skill}/helper.sh":*)']}})]
            command += ["-p", "/permission-fixture:permission-fixture"]
        try:
            if interactive:
                transcript = drive_terminal(command, env, cwd, state, case.second_turn)
                stderr = ""
                returncode = None
            elif client == "claude" and case.second_turn:
                transcript, stderr, returncode = drive_claude_turns(command, env, cwd, state)
            else:
                result = subprocess.run(
                    command, cwd=cwd, env=env, capture_output=True, text=True, timeout=40
                )
                transcript, stderr, returncode = result.stdout, result.stderr, result.returncode
            effects = {p.name: p.read_text() for p in skill.glob("*.effect")}
            cwd_preserved = any(
                str(cwd) in str(result.get("content", "")).splitlines()
                for result in state["results"]
            )
            permission_denials = []
            for line in transcript.splitlines():
                if not line.startswith("{"):
                    continue
                event = json.loads(line)
                if event.get("subtype") == "permission_denied":
                    permission_denials.append(event)
            next_turn = None
            if case.second_turn:
                last_result = str(state["results"][-1:]).lower()
                if "denied" in last_result or "requires approval" in last_result:
                    next_turn = "blocked"
                elif state["second_completed"] and "helper-executed" in last_result:
                    next_turn = "executed"
                else:
                    next_turn = "inconclusive"
            prompted = any(prompt in transcript for prompt in (
                "Do you want to allow", "Do you want to run this command?", "Allow tool",
            ))
            if effects and not cwd_preserved:
                outcome = "inconclusive"
            elif effects or state["url_requests"]:
                outcome = "executed"
            elif permission_denials or prompted or any("denied" in str(r).lower() for r in state["results"]):
                outcome = "blocked"
            else:
                outcome = "inconclusive"
            return {
                "case": case.name, "client": client, "mode": "interactive" if interactive else "headless",
                "rule": rule, "command": command, "cwd": str(cwd),
                "path_access": case.path_access, "returncode": returncode,
                "working_directory_preserved": cwd_preserved if effects else None,
                "effects": effects, "provider": state, "transcript": transcript, "stderr": stderr,
                "permission_denials": permission_denials,
                "next_turn_outcome": next_turn,
                "outcome": outcome,
            }
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=("claude", "copilot"), required=True)
    parser.add_argument("--interactive", action="store_true", help="Copilot PTY mode. Only fixture-folder trust is accepted.")
    parser.add_argument("--case", action="append", choices=[case.name for case in CASES])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.interactive and args.client != "copilot":
        parser.error("Claude probes use permission-enforced print mode.")
    executable = shutil.which(args.client)
    if not executable:
        parser.error(f"{args.client} executable not found")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    version = subprocess.check_output([executable, "--version"], text=True).strip()
    verifier_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    summaries = []
    for case in CASES:
        if args.case and case.name not in args.case:
            continue
        if case.second_turn and not args.interactive and args.client == "copilot":
            summaries.append({"case": case.name, "outcome": "unverified", "reason": "Requires the interactive multi-turn driver."})
            continue
        report = probe(executable, args.client, case, args.interactive)
        report["version"] = version
        report["verifier_sha256"] = verifier_sha256
        (args.output_dir / f"{case.name}.json").write_text(json.dumps(report, indent=2) + "\n")
        summaries.append({
            "case": case.name, "outcome": report["outcome"],
            "effects": report["effects"], "next_turn_outcome": report["next_turn_outcome"],
            "working_directory_preserved": report["working_directory_preserved"],
        })
        print(json.dumps(summaries[-1]), flush=True)
    (args.output_dir / "summary.json").write_text(json.dumps({
        "version": version, "verifier_sha256": verifier_sha256, "results": summaries,
    }, indent=2) + "\n")
    return int(any(
        result["outcome"] == "inconclusive" or result.get("next_turn_outcome") == "inconclusive"
        for result in summaries
    ))


if __name__ == "__main__":
    raise SystemExit(main())

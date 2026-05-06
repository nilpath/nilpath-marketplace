"""Run Claude CLI in headless mode and collect tool call events from stream-json output."""

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ToolCall:
    name: str
    input: dict


def run_skill_test(prompt: str, context_dir: Path | None, plugin_dir: Path) -> list[ToolCall]:
    """
    Invoke Claude CLI with the given prompt and return the ordered list of tool calls made.

    Args:
        prompt: The prompt to send to Claude.
        context_dir: Optional directory whose contents are copied into the temp working dir.
        plugin_dir: Path to the local plugin directory (passed via --plugin-dir).
    """
    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path(tmp)
        if context_dir and context_dir.exists():
            for item in context_dir.iterdir():
                dest = cwd / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--no-session-persistence",
            "--permission-mode", "bypassPermissions",
            "--plugin-dir", str(plugin_dir),
        ]

        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=600,
        )

        return _parse_tool_calls(result.stdout)


def _parse_tool_calls(stream_output: str) -> list[ToolCall]:
    calls = []
    for line in stream_output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") != "assistant":
            continue

        message = event.get("message", {})
        for block in message.get("content", []):
            if block.get("type") == "tool_use":
                calls.append(ToolCall(name=block["name"], input=block.get("input", {})))

    return calls

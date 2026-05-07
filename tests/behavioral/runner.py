"""Run Claude CLI in headless mode and capture the assistant transcript."""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Turn:
    """One assistant content block: either text or a tool_use call (never both)."""

    text: str | None = None
    tool_call_name: str | None = None
    tool_call_input: dict | None = None


def run_skill_test(
    prompt: str,
    inline_context: dict[str, str] | None,
    plugin_dir: Path,
) -> list[Turn]:
    """Invoke Claude CLI with the given prompt and return the assistant transcript.

    Args:
        prompt: The prompt to send to Claude.
        inline_context: Optional mapping of relative filename -> file content. Each entry
            is written into the temp working dir before Claude is invoked. Use this to
            plant fixture files (e.g. plan.md, CLAUDE.md, sample source) the skill needs.
        plugin_dir: Path to the local plugin directory (passed via --plugin-dir).
    """
    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path(tmp)
        for rel_path, content in (inline_context or {}).items():
            dest = cwd / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content)

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

        return _parse_transcript(result.stdout)


def _parse_transcript(stream_output: str) -> list[Turn]:
    transcript: list[Turn] = []
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
            block_type = block.get("type")
            if block_type == "text":
                text = (block.get("text") or "").strip()
                if text:
                    transcript.append(Turn(text=text))
            elif block_type == "tool_use":
                transcript.append(
                    Turn(
                        tool_call_name=block.get("name"),
                        tool_call_input=block.get("input", {}),
                    )
                )

    return transcript

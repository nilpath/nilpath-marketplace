"""Run bounded Claude fixtures and capture requested evidence before disposal."""

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


@dataclass
class ToolResult:
    tool_use_id: str
    content: object
    is_error: bool


@dataclass
class Observation:
    calls: list[ToolCall]
    results: list[ToolResult]
    final_output: str
    artifacts: dict[str, bytes | None]
    completed: bool = False


class FixtureFailure(RuntimeError):
    """Keep selected fixture evidence after the temporary workspace is disposed."""

    def __init__(self, message: str, artifacts: dict[str, bytes | None]):
        super().__init__(message)
        self.artifacts = artifacts


def _capture_artifacts(cwd: Path, artifact_paths: tuple[str, ...]) -> dict[str, bytes | None]:
    artifacts = {}
    for relative in artifact_paths:
        path = (cwd / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(cwd.resolve()):
            raise ValueError(f"Artifact must stay inside the fixture workspace: {relative}")
        if path.exists() and not path.is_file():
            raise ValueError(f"Artifact is not a file: {relative}")
        artifacts[relative] = path.read_bytes() if path.exists() else None
    return artifacts


def run_skill_test(prompt: str, context_dir: Path | None, plugin_dirs: list[Path]) -> list[ToolCall]:
    """Preserve the invocation-only interface for existing fixtures."""
    return run_skill_observation(prompt, context_dir, plugin_dirs).calls


def run_skill_observation(
    prompt: str, context_dir: Path | None, plugin_dirs: list[Path],
    artifact_paths: tuple[str, ...] = (),
) -> Observation:
    """Capture fixture-relative artifact bytes; missing files are explicitly None."""
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
        ]
        for plugin_dir in plugin_dirs:
            cmd += ["--plugin-dir", str(plugin_dir)]

        try:
            result = subprocess.run(
                cmd, cwd=str(cwd), capture_output=True, text=True, timeout=900,
            )
        except subprocess.TimeoutExpired as error:
            raise FixtureFailure("Claude fixture exceeded its time budget",
                                 _capture_artifacts(cwd, artifact_paths)) from error

        artifacts = _capture_artifacts(cwd, artifact_paths)
        if result.returncode:
            try:
                _parse_observation(result.stdout)
            except (RuntimeError, ValueError) as error:
                raise FixtureFailure(f"Claude fixture failed ({result.returncode}): {error}", artifacts) from error
            reason = result.stderr.strip()[-512:] or "no final error result"
            raise FixtureFailure(f"Claude fixture failed ({result.returncode}): {reason}", artifacts)
        try:
            observation = _parse_observation(result.stdout)
        except (RuntimeError, ValueError) as error:
            raise FixtureFailure(str(error), artifacts) from error
        if not observation.completed:
            raise FixtureFailure("Claude fixture exited without a final result event", artifacts)
        observation.artifacts = artifacts
        return observation


def _parse_tool_calls(stream_output: str) -> list[ToolCall]:
    return _parse_observation(stream_output).calls


def _parse_observation(stream_output: str) -> Observation:
    calls = []
    results = []
    final_output = ""
    completed = False
    for line in stream_output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            if line.startswith("{"):
                raise ValueError("Malformed Claude stream event") from error
            continue

        if event.get("type") == "result":
            if event.get("is_error"):
                raise RuntimeError(f"Claude fixture returned an error: {event.get('result', 'unspecified error')}")
            final_output = event.get("result", "")
            if not isinstance(final_output, str):
                raise ValueError("Claude final result must be a string")
            completed = True
        elif event.get("type") in {"assistant", "user"}:
            message = event.get("message", {})
            for block in message.get("content", []):
                if block.get("type") == "tool_use":
                    calls.append(ToolCall(name=block["name"], input=block.get("input", {})))
                elif block.get("type") == "tool_result":
                    results.append(ToolResult(
                        tool_use_id=block["tool_use_id"], content=block.get("content"),
                        is_error=bool(block.get("is_error", False)),
                    ))

    return Observation(calls, results, final_output, {}, completed)

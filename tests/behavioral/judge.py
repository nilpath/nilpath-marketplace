"""LLM-as-judge: evaluate a recorded agent transcript against a yes/no rubric."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass

from .runner import Turn

DEFAULT_JUDGE_MODEL = "claude-haiku-4-5-20251001"
TURN_TEXT_LIMIT = 500
TURN_TOOL_INPUT_LIMIT = 300
JUDGE_TIMEOUT_SECONDS = 300


@dataclass
class JudgeVerdict:
    criterion: str
    verdict: str  # "PASS" or "FAIL"
    rationale: str


def run_judge(transcript: list[Turn], rubric: list[str]) -> list[JudgeVerdict]:
    """Ask Claude (Haiku by default) to evaluate the transcript against each rubric item.

    The model is read from JUDGE_MODEL env var (default: Haiku 4.5). This makes the
    same code work against a local LM Studio backend by setting JUDGE_MODEL +
    ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN.
    """
    if not rubric:
        return []

    rendered_transcript = _render_transcript(transcript)
    prompt = _build_judge_prompt(rendered_transcript, rubric)
    model = os.environ.get("JUDGE_MODEL", DEFAULT_JUDGE_MODEL)

    cmd = [
        "claude",
        "-p", prompt,
        "--model", model,
        "--output-format", "json",
        "--no-session-persistence",
        "--permission-mode", "bypassPermissions",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=JUDGE_TIMEOUT_SECONDS,
    )

    return _parse_verdicts(result.stdout, rubric)


def _render_transcript(transcript: list[Turn]) -> str:
    lines = []
    for turn in transcript:
        if turn.text is not None:
            text = turn.text[:TURN_TEXT_LIMIT]
            if len(turn.text) > TURN_TEXT_LIMIT:
                text += "…"
            lines.append(f"Text: {text}")
        elif turn.tool_call_name is not None:
            input_str = json.dumps(turn.tool_call_input, default=str)
            if len(input_str) > TURN_TOOL_INPUT_LIMIT:
                input_str = input_str[:TURN_TOOL_INPUT_LIMIT] + "…"
            lines.append(f"Tool: {turn.tool_call_name}({input_str})")
    return "\n".join(lines)


def _build_judge_prompt(transcript: str, rubric: list[str]) -> str:
    numbered_rubric = "\n".join(f"{i}. {item}" for i, item in enumerate(rubric, start=1))
    return f"""You are evaluating a recorded agent session against a rubric of yes/no rules.

For each numbered rubric item, decide PASS (the rule held) or FAIL (the rule was violated). Cite specific turns from the transcript when justifying FAIL. Do not be lenient — if the transcript does not clearly support PASS, return FAIL with the reason.

Output STRICT JSON ONLY (no prose, no markdown, no code fences). The JSON must be an array with exactly {len(rubric)} entries, in rubric order. Each entry has the shape:

{{"criterion": "<the rubric statement>", "verdict": "PASS" | "FAIL", "rationale": "<one sentence>"}}

Rubric:
{numbered_rubric}

Transcript:
{transcript}
"""


def _parse_verdicts(stdout: str, rubric: list[str]) -> list[JudgeVerdict]:
    """Parse the judge's CLI output into JudgeVerdict objects.

    The CLI returns a JSON envelope with a `result` field containing the model's text
    output. We extract that, then parse the inner JSON array.
    """
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Judge CLI output was not JSON.\nstdout:\n{stdout}") from e

    inner = envelope.get("result", "")
    if not inner:
        raise RuntimeError(f"Judge CLI envelope missing `result`.\nstdout:\n{stdout}")

    verdicts_json = _extract_json_array(inner)
    try:
        items = json.loads(verdicts_json)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Judge inner output was not a JSON array.\nresult:\n{inner}") from e

    if not isinstance(items, list):
        raise RuntimeError(f"Judge output was not a JSON array.\nparsed: {items!r}")

    verdicts = []
    for i, item in enumerate(items):
        verdict = (item.get("verdict") or "").upper()
        if verdict not in ("PASS", "FAIL"):
            raise RuntimeError(f"Invalid verdict for entry {i}: {item!r}")
        verdicts.append(
            JudgeVerdict(
                criterion=item.get("criterion") or (rubric[i] if i < len(rubric) else ""),
                verdict=verdict,
                rationale=item.get("rationale") or "",
            )
        )
    return verdicts


def _extract_json_array(text: str) -> str:
    """Strip surrounding code fences or prose and return the first JSON array substring."""
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    bare = re.search(r"\[.*\]", text, re.DOTALL)
    if bare:
        return bare.group(0)
    return text

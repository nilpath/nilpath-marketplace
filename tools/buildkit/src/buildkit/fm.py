"""Frontmatter split/process/serialize.

Rendered templates are never trusted: the frontmatter is parsed (hard failure
on invalid YAML), build-only keys are stripped, canonical tools/model/reasoning
are translated per harness, and the remaining keys are validated against the
harness's allowed list before re-serialization.
"""

from __future__ import annotations

import yaml

from .config import HarnessConfig, SourceConfig
from .toolmap import resolve_model_tier, split_tool_list, translate_tools

BUILD_ONLY_KEYS = ("targets", "category")


class FrontmatterError(Exception):
    pass


def split_document(text: str) -> tuple[dict, str]:
    """Split a rendered markdown document into (frontmatter dict, body)."""
    if not text.startswith("---"):
        raise FrontmatterError("document does not start with '---' frontmatter")
    parts = text.split("\n---", 2)
    # parts[0] == '---' opening line remainder; find closing fence properly
    lines = text.splitlines(keepends=True)
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.rstrip("\n") == "---":
            end = i
            break
    if end is None:
        raise FrontmatterError("frontmatter closing '---' not found")
    fm_text = "".join(lines[1:end])
    body = "".join(lines[end + 1:])
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"invalid frontmatter YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter is not a mapping")
    return data, body


def _dump_scalar(value) -> str:
    """Serialize a single YAML value on one line, plain where possible."""
    if isinstance(value, str):
        value = value.strip()
    text = yaml.safe_dump(
        value, default_flow_style=True, width=10**6, allow_unicode=True
    ).strip()
    if text.endswith("\n..."):
        text = text[: -len("\n...")]
    return text.strip()


def dump_frontmatter(data: dict) -> str:
    """Serialize frontmatter preserving key order, matching repo style:
    single-line plain scalars, block lists for list values."""
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_dump_scalar(item)}")
        elif isinstance(value, dict):
            lines.append(f"{key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"  {sub_key}: {_dump_scalar(sub_value)}")
        else:
            lines.append(f"{key}: {_dump_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def dump_agent_toml(data: dict, body: str) -> tuple[str, list[str]]:
    """Serialize an agent as a Codex custom-agent TOML file.

    The markdown body becomes `developer_instructions` as a TOML multi-line
    literal string (no escape processing), so only a literal ''' inside the
    body needs defusing."""
    warnings: list[str] = []

    def quote(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    lines = [f"{key} = {quote(str(value))}" for key, value in data.items()]
    body = body.strip("\n")
    if "'''" in body:
        warnings.append("agent body contains ''' — rewritten to '' ' for TOML")
        body = body.replace("'''", "'' '")
    lines.append(f"developer_instructions = '''\n{body}\n'''")
    return "\n".join(lines) + "\n", warnings


def process_frontmatter(
    data: dict,
    kind: str,
    harness: HarnessConfig,
    cfg: SourceConfig,
    component: str,
) -> tuple[dict, list[str]]:
    """Adapt canonical frontmatter for one harness. Returns (data, warnings)."""
    warnings: list[str] = []
    schema = harness.frontmatter_schema(kind)
    allowed = set(schema.get("allowed", []))
    required = schema.get("required", [])
    drop_keys = set(schema.get("drop", []))
    key_for_tools = schema.get("key_for_tools")

    out: dict = {}
    for key, value in data.items():
        if key in BUILD_ONLY_KEYS:
            continue

        if key == "tools":
            entries = split_tool_list(value)
            translated, tool_warnings = translate_tools(entries, harness, cfg)
            warnings.extend(f"{component}: {w}" for w in tool_warnings)
            if key_for_tools and translated:
                if harness.tools_format == "list":
                    out[key_for_tools] = translated
                else:
                    out[key_for_tools] = ", ".join(translated)
            continue

        if key == "model":
            resolved, model_warnings = resolve_model_tier(str(value), harness, cfg)
            warnings.extend(f"{component}: {w}" for w in model_warnings)
            if resolved is not None:
                out["model"] = resolved
            continue

        if key == "reasoning":
            reasoning_key = harness.reasoning_key
            if not reasoning_key:
                warnings.append(
                    f"{component}: reasoning level dropped ({harness.id} has no reasoning setting)"
                )
                continue
            level = str(value)
            if level not in cfg.reasoning_levels:
                raise FrontmatterError(
                    f"{component}: unknown reasoning level '{level}' (expected one of {cfg.reasoning_levels})"
                )
            out[reasoning_key] = harness.reasoning_map.get(level, level)
            continue

        translate = schema.get("translate", {})
        if key in translate:
            spec = translate[key]
            value_map = spec.get("map", {})
            if str(value) in value_map:
                out[spec["key"]] = value_map[str(value)]
            else:
                warnings.append(
                    f"{component}: '{key}: {value}' has no {harness.id} translation; dropped"
                )
            continue

        if key in drop_keys:
            warnings.append(f"{component}: key '{key}' dropped (not supported by {harness.id})")
            continue
        out[key] = value

    unknown = [k for k in out if k not in allowed]
    if unknown:
        raise FrontmatterError(
            f"{component}: keys {unknown} not allowed for {harness.id} {kind} "
            f"(allowed: {sorted(allowed)})"
        )
    missing = [k for k in required if k not in out]
    if missing:
        raise FrontmatterError(f"{component}: missing required keys {missing} for {harness.id}")
    return out, warnings

"""Parsing and translation of the canonical tool vocabulary.

Canonical entries look like:
    shell                   plain tool
    shell(git add:*)        scoped tool
    subagent(code-reviewer) scoped delegation
    claude:mcp__context7__query-docs
                            harness-prefixed passthrough: rendered verbatim on
                            that harness only, dropped everywhere else
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import HarnessConfig, SourceConfig


@dataclass
class ToolEntry:
    name: str
    scope: str | None = None
    passthrough_harness: str | None = None  # set for "harness:raw" entries

    def canonical(self) -> str:
        if self.passthrough_harness:
            return f"{self.passthrough_harness}:{self.name}"
        return f"{self.name}({self.scope})" if self.scope else self.name


def parse_entry(entry: str) -> ToolEntry:
    entry = entry.strip()
    if ":" in entry and "(" not in entry.split(":", 1)[0]:
        prefix, rest = entry.split(":", 1)
        # Distinguish "claude:raw" passthrough from scopes (scopes always sit in parens)
        if prefix.isalpha() and prefix.islower():
            return ToolEntry(name=rest, passthrough_harness=prefix)
    if "(" in entry and entry.endswith(")"):
        name, scope = entry.split("(", 1)
        return ToolEntry(name=name.strip(), scope=scope[:-1])
    return ToolEntry(name=entry)


def split_tool_list(value) -> list[str]:
    """Accept a YAML list or a comma/space separated string; respect parens."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value)
    sep = "," if "," in text else " "
    parts, buf, depth = [], "", 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            if buf.strip():
                parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts


def translate_tools(
    entries: list[str],
    harness: HarnessConfig,
    cfg: SourceConfig,
) -> tuple[list[str], list[str]]:
    """Translate canonical entries to a harness's vocabulary.

    Returns (translated entries, warnings).
    """
    out: list[str] = []
    warnings: list[str] = []
    for raw in entries:
        entry = parse_entry(raw)

        if entry.passthrough_harness:
            if entry.passthrough_harness == harness.id:
                out.append(entry.name)
            continue  # silently dropped elsewhere: passthrough is harness-scoped by design

        if entry.name not in cfg.canonical_tools:
            raise ValueError(f"unknown canonical tool '{entry.name}' (entry: {raw!r})")
        if entry.name in harness.tool_unmappable:
            warnings.append(f"tool '{entry.name}' has no {harness.id} equivalent; dropped")
            continue
        mapped = harness.tool_map.get(entry.name)
        if mapped is None:
            if harness.tool_map:  # mapped vocabulary exists but lacks this tool
                warnings.append(f"tool '{entry.name}' not mapped for {harness.id}; dropped")
            continue  # empty map (codex): strip silently
        if entry.scope and harness.keep_tool_scopes:
            out.append(f"{mapped}({entry.scope})")
        else:
            out.append(mapped)

    if harness.tool_dedupe:
        seen: set[str] = set()
        deduped = []
        for item in out:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        out = deduped
    return out, warnings


def resolve_model_tier(tier: str, harness: HarnessConfig, cfg: SourceConfig):
    """Resolve a canonical tier via the harness map, falling back to the
    nearest defined neighbour on the ordered scale (lower first on ties)."""
    model_map = harness.model_map
    if not model_map:
        return None, [f"model tier '{tier}' dropped: {harness.id} defines no model map"]
    if tier in model_map:
        return model_map[tier], []
    tiers = cfg.model_tiers
    if tier not in tiers:
        return None, [f"unknown model tier '{tier}' (expected one of {tiers})"]
    idx = tiers.index(tier)
    for distance in range(1, len(tiers)):
        for neighbour_idx in (idx - distance, idx + distance):
            if 0 <= neighbour_idx < len(tiers) and tiers[neighbour_idx] in model_map:
                neighbour = tiers[neighbour_idx]
                return model_map[neighbour], [
                    f"model tier '{tier}' not mapped for {harness.id}; using nearest tier '{neighbour}'"
                ]
    return None, [f"model tier '{tier}' could not be resolved for {harness.id}"]

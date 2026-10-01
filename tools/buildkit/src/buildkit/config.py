"""Load and expose the authored configuration under src/."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class HarnessConfig:
    id: str
    raw: dict

    @property
    def output(self) -> dict:
        return self.raw.get("output", {})

    @property
    def skill_root_template(self) -> str:
        return self.raw.get("paths", {}).get("skill_root", ".")

    def frontmatter_schema(self, kind: str) -> dict:
        return self.raw.get("frontmatter", {}).get(kind, {})

    @property
    def tool_map(self) -> dict:
        return self.raw.get("tools", {}).get("map", {})

    @property
    def tool_unmappable(self) -> list[str]:
        return self.raw.get("tools", {}).get("unmappable", [])

    @property
    def tool_dedupe(self) -> bool:
        return bool(self.raw.get("tools", {}).get("dedupe", False))

    @property
    def tools_format(self) -> str:
        """How the translated tool list is rendered: 'comma' string or 'list'."""
        return self.raw.get("tools", {}).get("format", "comma")

    @property
    def keep_tool_scopes(self) -> bool:
        return bool(self.raw.get("tools", {}).get("keep_scopes", False))

    @property
    def model_map(self) -> dict:
        return self.raw.get("models", {}).get("map", {})

    @property
    def reasoning_key(self) -> str | None:
        return self.raw.get("reasoning", {}).get("key")

    @property
    def reasoning_map(self) -> dict:
        return self.raw.get("reasoning", {}).get("map", {})

    def supports_kind(self, kind: str) -> bool:
        dir_key = {"skill": "skills_dir", "agent": "agents_dir"}[kind]
        return dir_key in self.output


@dataclass
class SourceConfig:
    root: Path  # the src/ directory
    repo_root: Path
    plugin: dict
    tools: dict  # canonical vocabulary (tools.yaml)
    harnesses: dict[str, HarnessConfig] = field(default_factory=dict)

    @property
    def canonical_tools(self) -> dict:
        return self.tools.get("tools", {})

    @property
    def model_tiers(self) -> list[str]:
        return self.tools.get("models", {}).get("tiers", [])

    @property
    def reasoning_levels(self) -> list[str]:
        return self.tools.get("reasoning", {}).get("levels", [])


def load_config(repo_root: Path) -> SourceConfig:
    src = repo_root / "src"
    harness_dir = src / "harnesses"
    tools = yaml.safe_load((harness_dir / "tools.yaml").read_text())
    plugin = yaml.safe_load((src / "plugin.yaml").read_text())

    harnesses: dict[str, HarnessConfig] = {}
    for path in sorted(harness_dir.glob("*.yaml")):
        if path.name == "tools.yaml":
            continue
        raw = yaml.safe_load(path.read_text())
        harnesses[raw["id"]] = HarnessConfig(id=raw["id"], raw=raw)

    return SourceConfig(
        root=src,
        repo_root=repo_root,
        plugin=plugin,
        tools=tools,
        harnesses=harnesses,
    )

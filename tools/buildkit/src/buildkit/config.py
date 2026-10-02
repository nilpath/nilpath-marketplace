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
    def dist_root(self) -> str:
        """Repo-relative root of this harness's generated tree (e.g. dist/claude)."""
        return self.output["dist_root"]

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

    @property
    def agent_format(self) -> str:
        """Output format for agents: 'markdown' (frontmatter + body) or 'toml'."""
        return self.output.get("agent_format", "markdown")

    def supports_kind(self, kind: str) -> bool:
        dir_key = {"skill": "skills_dir", "agent": "agents_dir"}[kind]
        return dir_key in self.output


@dataclass
class PluginConfig:
    """One plugin's metadata (marketplace defaults overlaid with plugin.yaml)."""

    src_dir: Path
    meta: dict

    @property
    def name(self) -> str:
        return self.meta["name"]

    @property
    def version(self) -> str:
        return self.meta["version"]

    @property
    def mcp(self) -> dict:
        return self.meta.get("mcp", {})


@dataclass
class SourceConfig:
    root: Path  # the src/ directory
    repo_root: Path
    marketplace: dict
    plugins: list[PluginConfig]
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
    marketplace = yaml.safe_load((src / "marketplace.yaml").read_text())
    defaults = marketplace.get("defaults", {})

    plugins: list[PluginConfig] = []
    for plugin_yaml in sorted((src / "plugins").glob("*/plugin.yaml")):
        meta = {**defaults, **yaml.safe_load(plugin_yaml.read_text())}
        plugins.append(PluginConfig(src_dir=plugin_yaml.parent, meta=meta))

    harnesses: dict[str, HarnessConfig] = {}
    for path in sorted(harness_dir.glob("*.yaml")):
        if path.name == "tools.yaml":
            continue
        raw = yaml.safe_load(path.read_text())
        harnesses[raw["id"]] = HarnessConfig(id=raw["id"], raw=raw)

    return SourceConfig(
        root=src,
        repo_root=repo_root,
        marketplace=marketplace,
        plugins=plugins,
        tools=tools,
        harnesses=harnesses,
    )

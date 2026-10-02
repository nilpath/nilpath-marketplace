"""Generate per-plugin manifests and the root marketplace registries."""

from __future__ import annotations

import json
from pathlib import Path

from .config import PluginConfig, SourceConfig

AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _display_name(name: str) -> str:
    return name.replace("-", " ").title()


def write_claude_plugin_manifest(plugin_dir: Path, plugin: PluginConfig) -> list[Path]:
    meta = plugin.meta
    manifest = {
        "name": meta["name"],
        "version": meta["version"],
        "description": meta["description"],
        "author": meta["author"],
        "homepage": meta["homepage"],
        "repository": meta["repository"],
        "license": meta["license"],
        "keywords": meta.get("keywords", []),
    }
    paths = {plugin_dir / ".claude-plugin" / "plugin.json": manifest}
    if plugin.mcp:
        paths[plugin_dir / ".mcp.json"] = plugin.mcp
    for path, data in paths.items():
        _write_json(path, data)
    return list(paths)


def write_copilot_plugin_manifest(plugin_dir: Path, plugin: PluginConfig) -> list[Path]:
    meta = plugin.meta
    manifest = {
        "$schema": AGENT_PLUGINS_SCHEMA,
        "name": meta["name"],
        "version": meta["version"],
        "description": meta["description"],
        "author": meta["author"],
        "license": meta["license"],
        "skills": "./skills/",
        "keywords": meta.get("keywords", []),
    }
    paths = {plugin_dir / "plugin.json": manifest}
    if plugin.mcp:
        paths[plugin_dir / "mcp.json"] = {"mcpServers": plugin.mcp}
    for path, data in paths.items():
        _write_json(path, data)
    return list(paths)


def write_codex_plugin_manifest(
    plugin_dir: Path, plugin: PluginConfig, agent_files: list[str]
) -> list[Path]:
    meta = plugin.meta
    manifest = {
        "name": meta["name"],
        "version": meta["version"],
        "description": meta["description"],
        "skills": "./skills/",
        "author": meta["author"],
        "keywords": meta.get("keywords", []),
        "interface": {
            "displayName": _display_name(meta["name"]),
            "shortDescription": meta["description"][:100],
            "longDescription": meta["description"],
            "category": meta.get("category", "Productivity"),
        },
    }
    if agent_files:
        manifest["components"] = {
            "agents": [f"agents/{name}" for name in sorted(agent_files)],
        }
    paths = {plugin_dir / ".codex-plugin" / "plugin.json": manifest}
    if plugin.mcp:
        paths[plugin_dir / ".codex-mcp.json"] = plugin.mcp
    for path, data in paths.items():
        _write_json(path, data)
    return list(paths)


def write_marketplace_registries(
    out_root: Path, cfg: SourceConfig, included: dict[str, list] | None = None
) -> list[Path]:
    """Write the root registries. `included` maps harness id -> plugins that
    actually have components for that harness (empty plugins are omitted)."""
    marketplace = cfg.marketplace
    claude_plugins = included.get("claude", cfg.plugins) if included else cfg.plugins
    codex_plugins = included.get("codex", cfg.plugins) if included else cfg.plugins
    copilot_plugins = included.get("copilot", cfg.plugins) if included else cfg.plugins
    # VS Code discovers marketplace plugins via .github/plugin/marketplace.json
    # (it does NOT read the Claude-format registry); source paths are
    # repo-relative and may point into dist/.
    copilot_registry = {
        "name": marketplace["name"],
        "metadata": {
            "description": marketplace["description"],
            "version": marketplace["version"],
        },
        "owner": marketplace["owner"],
        "plugins": [
            {
                "name": p.name,
                "source": f"{cfg.harnesses['copilot'].dist_root}/plugins/{p.name}",
                "description": p.meta["description"],
                "version": p.version,
                "author": p.meta["author"],
                "license": p.meta["license"],
                "keywords": p.meta.get("keywords", []),
            }
            for p in copilot_plugins
        ],
    }
    claude_registry = {
        "name": marketplace["name"],
        "owner": marketplace["owner"],
        "metadata": {
            "description": marketplace["description"],
            "version": marketplace["version"],
        },
        "plugins": [
            {
                "name": p.name,
                "source": f"./{cfg.harnesses['claude'].dist_root}/plugins/{p.name}",
                "description": p.meta["description"],
                "version": p.version,
                "author": p.meta["author"],
                "homepage": p.meta["homepage"],
                "tags": p.meta.get("keywords", []),
            }
            for p in claude_plugins
        ],
    }
    codex_registry = {
        "name": marketplace["name"],
        "interface": {"displayName": _display_name(marketplace["name"])},
        "plugins": [
            {
                "name": p.name,
                "source": {
                    "source": "local",
                    "path": f"./{cfg.harnesses['codex'].dist_root}/plugins/{p.name}",
                },
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": p.meta.get("category", "Productivity"),
            }
            for p in codex_plugins
        ],
    }
    paths = {
        out_root / ".claude-plugin" / "marketplace.json": claude_registry,
        out_root / ".agents" / "plugins" / "marketplace.json": codex_registry,
        out_root / ".github" / "plugin" / "marketplace.json": copilot_registry,
    }
    for path, data in paths.items():
        _write_json(path, data)
    return list(paths)

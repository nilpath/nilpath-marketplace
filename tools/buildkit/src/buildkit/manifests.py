"""Generate per-harness manifest files from src/plugin.yaml."""

from __future__ import annotations

import json
from pathlib import Path

AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def plugin_dir(out_root: Path, plugin: dict) -> Path:
    return out_root / "plugins" / plugin["name"]


def write_claude_manifests(out_root: Path, plugin: dict) -> list[Path]:
    pdir = plugin_dir(out_root, plugin)
    plugin_json = {
        "name": plugin["name"],
        "version": plugin["version"],
        "description": plugin["description"],
        "author": plugin["author"],
        "homepage": plugin["homepage"],
        "repository": plugin["repository"],
        "license": plugin["license"],
        "keywords": plugin.get("keywords", []),
    }
    marketplace = plugin["marketplace"]
    marketplace_json = {
        "name": marketplace["name"],
        "owner": marketplace["owner"],
        "metadata": {
            "description": marketplace["description"],
            "version": marketplace["version"],
        },
        "plugins": [
            {
                "name": plugin["name"],
                "source": f"./plugins/{plugin['name']}",
                "description": plugin["description"],
                "version": plugin["version"],
                "author": plugin["author"],
                "homepage": plugin["homepage"],
                "tags": plugin.get("keywords", []),
            }
        ],
    }
    paths = {
        pdir / ".claude-plugin" / "plugin.json": plugin_json,
        out_root / ".claude-plugin" / "marketplace.json": marketplace_json,
        pdir / ".mcp.json": plugin.get("mcp", {}),
    }
    for path, data in paths.items():
        _write_json(path, data)
    return list(paths)


def write_copilot_manifests(out_root: Path, plugin: dict) -> list[Path]:
    pdir = plugin_dir(out_root, plugin)
    plugin_json = {
        "$schema": AGENT_PLUGINS_SCHEMA,
        "name": plugin["name"],
        "version": plugin["version"],
        "description": plugin["description"],
        "author": plugin["author"],
        "license": plugin["license"],
        "skills": "./skills-portable/",
        "keywords": plugin.get("keywords", []),
    }
    mcp_json = {"mcpServers": plugin.get("mcp", {})}
    paths = {
        pdir / "plugin.json": plugin_json,
        pdir / "mcp.json": mcp_json,
    }
    for path, data in paths.items():
        _write_json(path, data)
    return list(paths)


def write_codex_manifests(
    out_root: Path, plugin: dict, skills_index: list[dict], agent_files: list[str]
) -> list[Path]:
    pdir = plugin_dir(out_root, plugin)
    display_name = plugin["name"].replace("-", " ").title()
    plugin_json = {
        "name": plugin["name"],
        "version": plugin["version"],
        "description": plugin["description"],
        "skills": "./skills-portable/",
        "components": {
            "agents": [f"agents-codex/{name}" for name in sorted(agent_files)],
        },
        "author": plugin["author"],
        "keywords": plugin.get("keywords", []),
        "interface": {
            "displayName": display_name,
            "shortDescription": plugin["description"][:100],
            "longDescription": plugin["description"],
            "category": plugin.get("category", "Productivity"),
        },
    }
    marketplace = plugin["marketplace"]
    registry_json = {
        "name": marketplace["name"],
        "interface": {"displayName": marketplace["name"].replace("-", " ").title()},
        "plugins": [
            {
                "name": plugin["name"],
                "source": {"source": "local", "path": f"./plugins/{plugin['name']}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": plugin.get("category", "Productivity"),
            }
        ],
    }
    paths = {
        pdir / ".codex-plugin" / "plugin.json": plugin_json,
        pdir / ".codex-mcp.json": plugin.get("mcp", {}),
        out_root / ".agents" / "plugins" / "marketplace.json": registry_json,
        out_root / ".well-known" / "skills" / "index.json": {"skills": skills_index},
    }
    for path, data in paths.items():
        _write_json(path, data)
    return list(paths)

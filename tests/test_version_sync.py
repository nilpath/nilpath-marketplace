import json

import pytest
import yaml

from paths import CHANGELOG_MD, MARKETPLACE_JSON, PLUGIN_DIRS, SRC_PLUGINS_DIR


def _marketplace_plugins() -> dict[str, dict]:
    data = json.loads(MARKETPLACE_JSON.read_text())
    return {p["name"]: p for p in data.get("plugins", [])}


def _src_plugins() -> dict[str, dict]:
    return {
        f.parent.name: yaml.safe_load(f.read_text())
        for f in sorted(SRC_PLUGINS_DIR.glob("*/plugin.yaml"))
    }


def test_marketplace_lists_every_plugin():
    marketplace = set(_marketplace_plugins())
    src = set(_src_plugins())
    dist = {p.name for p in PLUGIN_DIRS}
    assert marketplace == src == dist, (
        f"plugin sets diverge: marketplace={sorted(marketplace)}, "
        f"src={sorted(src)}, dist={sorted(dist)}"
    )


@pytest.mark.parametrize("plugin_dir", PLUGIN_DIRS, ids=lambda p: p.name)
def test_plugin_version_sync(plugin_dir):
    manifest = json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text())
    src_version = _src_plugins()[plugin_dir.name]["version"]
    market_version = _marketplace_plugins()[plugin_dir.name]["version"]
    assert manifest["version"] == src_version == market_version, (
        f"{plugin_dir.name}: plugin.json={manifest['version']}, "
        f"src={src_version}, marketplace={market_version}"
    )


@pytest.mark.parametrize("plugin_dir", PLUGIN_DIRS, ids=lambda p: p.name)
def test_changelog_contains_plugin_version(plugin_dir):
    version = _src_plugins()[plugin_dir.name]["version"]
    changelog = CHANGELOG_MD.read_text()
    assert version in changelog, f"Version '{version}' not found in CHANGELOG.md"


@pytest.mark.parametrize("plugin_dir", PLUGIN_DIRS, ids=lambda p: p.name)
def test_plugin_readme_exists(plugin_dir):
    assert (plugin_dir / "README.md").exists(), f"{plugin_dir.name}: missing README.md in dist"

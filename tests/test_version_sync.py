import json
import re

import pytest
from buildkit.config import load_config

from paths import ROOT, RENDERED_ROOT


def test_current_readme_version_fields_match_source_exactly():
    plugins = load_config(ROOT).plugins
    cells = re.findall(
        r"^\| \*\*([a-z0-9-]+)\*\* \| ([0-9]+\.[0-9]+\.[0-9]+) \|",
        (ROOT / "README.md").read_text(), re.M,
    )
    assert len(cells) == len(plugins)
    assert dict(cells) == {plugin.name: plugin.version for plugin in plugins}
    for plugin in plugins:
        readme = plugin.src_dir / "README.md"
        headers = re.findall(r"^Version: \*\*([^*]+)\*\*$", readme.read_text(), re.M)
        if headers:
            assert headers == [plugin.version]


@pytest.mark.parametrize("harness,manifest,registry_path", [
    ("claude", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"),
    ("copilot", "plugin.json", ".github/plugin/marketplace.json"),
    ("codex", ".codex-plugin/plugin.json", ".agents/plugins/marketplace.json"),
])
def test_generated_manifests_and_registry_match_sources(harness, manifest, registry_path):
    cfg = load_config(ROOT)
    sources = {plugin.name: plugin.version for plugin in cfg.plugins}
    plugins = RENDERED_ROOT / cfg.harnesses[harness].dist_root / "plugins"
    actual = {}
    for plugin in sorted(plugins.iterdir()):
        data = json.loads((plugin / manifest).read_text())
        assert data["name"] == plugin.name
        actual[plugin.name] = data["version"]
        assert data["version"] == sources[plugin.name]
        assert (plugin / "README.md").is_file(), f"{plugin.name}: missing README.md"
    if harness == "claude":
        assert set(actual) == set(sources)
    registry = json.loads((RENDERED_ROOT / registry_path).read_text())
    assert sorted(entry["name"] for entry in registry["plugins"]) == sorted(actual)
    if harness != "codex":
        assert registry["metadata"]["version"] == cfg.marketplace["version"]
    for entry in registry["plugins"]:
        path = f"{cfg.harnesses[harness].dist_root}/plugins/{entry['name']}"
        if harness == "codex":
            assert entry["source"] == {"source": "local", "path": f"./{path}"}
        else:
            assert entry["source"] == (f"./{path}" if harness == "claude" else path)
            assert entry["version"] == actual[entry["name"]]

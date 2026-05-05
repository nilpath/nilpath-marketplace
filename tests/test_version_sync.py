import json
import re
from pathlib import Path
import pytest
from paths import ROOT, PLUGIN_DIR, SKILLS_DIR, AGENTS_DIR

PLUGIN_JSON = PLUGIN_DIR / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = ROOT / ".claude-plugin" / "marketplace.json"
CHANGELOG_MD = PLUGIN_DIR / "CHANGELOG.md"
README_MD = PLUGIN_DIR / "README.md"

AGENTS_COUNT_RE = re.compile(r"###\s+Agents\s*\((\d+)\)")
SKILLS_COUNT_RE = re.compile(r"###\s+Skills\s*\((\d+)\)")


def _plugin_version() -> str:
    data = json.loads(PLUGIN_JSON.read_text())
    return data["version"]


def _marketplace_version(plugin_name: str) -> str:
    data = json.loads(MARKETPLACE_JSON.read_text())
    for plugin in data.get("plugins", []):
        if plugin["name"] == plugin_name:
            return plugin["version"]
    raise KeyError(f"Plugin '{plugin_name}' not found in marketplace.json")


def _actual_skill_count() -> int:
    return sum(
        1 for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").exists()
    )


def _actual_agent_count() -> int:
    return sum(1 for _ in AGENTS_DIR.rglob("*.md"))


def test_plugin_version_matches_marketplace():
    plugin_ver = _plugin_version()
    market_ver = _marketplace_version("claude-code-tools")
    assert plugin_ver == market_ver, (
        f"plugin.json version '{plugin_ver}' != marketplace.json version '{market_ver}'"
    )


def test_changelog_contains_current_version():
    version = _plugin_version()
    changelog = CHANGELOG_MD.read_text()
    assert version in changelog, (
        f"Version '{version}' not found in CHANGELOG.md"
    )


def test_readme_skill_count_matches_actual():
    readme = README_MD.read_text()
    match = SKILLS_COUNT_RE.search(readme)
    assert match, "Could not find '### Skills (N)' heading in README.md"
    readme_count = int(match.group(1))
    actual = _actual_skill_count()
    assert readme_count == actual, (
        f"README.md says {readme_count} skills but found {actual} skill directories"
    )


def test_readme_agent_count_matches_actual():
    readme = README_MD.read_text()
    match = AGENTS_COUNT_RE.search(readme)
    assert match, "Could not find '### Agents (N)' heading in README.md"
    readme_count = int(match.group(1))
    actual = _actual_agent_count()
    assert readme_count == actual, (
        f"README.md says {readme_count} agents but found {actual} agent files"
    )

from pathlib import Path

ROOT = Path(__file__).parent.parent

# The Claude harness render is the tree validated by the structure tests.
CLAUDE_PLUGINS_DIR = ROOT / "dist" / "claude" / "plugins"
PLUGIN_DIRS = sorted(p for p in CLAUDE_PLUGINS_DIR.iterdir() if p.is_dir())

SRC_PLUGINS_DIR = ROOT / "src" / "plugins"
MARKETPLACE_JSON = ROOT / ".claude-plugin" / "marketplace.json"
CHANGELOG_MD = ROOT / "CHANGELOG.md"


def all_skill_dirs() -> list[Path]:
    return sorted(
        skill_dir
        for plugin in PLUGIN_DIRS
        for skill_dir in (plugin / "skills").glob("*")
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists()
    )


def all_agent_files() -> list[Path]:
    return sorted(
        agent_file
        for plugin in PLUGIN_DIRS
        if (plugin / "agents").is_dir()
        for agent_file in (plugin / "agents").rglob("*.md")
    )

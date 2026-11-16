from pathlib import Path
from tempfile import TemporaryDirectory

from buildkit.build import build

ROOT = Path(__file__).parent.parent

_preview = TemporaryDirectory(prefix="nilpath-tests-")
RENDERED_ROOT = Path(_preview.name)
build(ROOT, out_root=RENDERED_ROOT)
CLAUDE_PLUGINS_DIR = RENDERED_ROOT / "dist" / "claude" / "plugins"
PLUGIN_DIRS = sorted(p for p in CLAUDE_PLUGINS_DIR.iterdir() if p.is_dir())

SRC_PLUGINS_DIR = ROOT / "src" / "plugins"
MARKETPLACE_JSON = RENDERED_ROOT / ".claude-plugin" / "marketplace.json"
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

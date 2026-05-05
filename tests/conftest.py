from pathlib import Path
import frontmatter
import pytest
from paths import SKILLS_DIR, AGENTS_DIR


def _load_frontmatter(path: Path) -> dict:
    post = frontmatter.load(str(path))
    return dict(post.metadata)


@pytest.fixture(scope="session")
def skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").exists())


@pytest.fixture(scope="session")
def agent_files() -> list[Path]:
    return sorted(AGENTS_DIR.rglob("*.md"))


@pytest.fixture(scope="session")
def skill_frontmatters(skill_dirs) -> dict[str, dict]:
    return {d.name: _load_frontmatter(d / "SKILL.md") for d in skill_dirs}


@pytest.fixture(scope="session")
def agent_frontmatters(agent_files) -> dict[str, dict]:
    return {f.stem: _load_frontmatter(f) for f in agent_files}


@pytest.fixture(scope="session")
def known_skill_names(skill_frontmatters) -> set[str]:
    return {fm["name"] for fm in skill_frontmatters.values() if "name" in fm}

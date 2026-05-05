import re
from pathlib import Path
import frontmatter
import pytest
from paths import SKILLS_DIR, AGENTS_DIR

SKILL_REF_RE = re.compile(r"Skill\(([^)]+)\)")


def _extract_skill_refs(value: str) -> list[str]:
    return SKILL_REF_RE.findall(value)


def _all_skill_names() -> set[str]:
    names = set()
    for skill_dir in SKILLS_DIR.iterdir():
        skill_md = skill_dir / "SKILL.md"
        if skill_dir.is_dir() and skill_md.exists():
            post = frontmatter.load(str(skill_md))
            if "name" in post.metadata:
                names.add(post.metadata["name"])
    return names


def _all_agent_names() -> set[str]:
    names = set()
    for agent_file in AGENTS_DIR.rglob("*.md"):
        post = frontmatter.load(str(agent_file))
        if "name" in post.metadata:
            names.add(post.metadata["name"])
    return names


@pytest.fixture(scope="module")
def known_skill_names() -> set[str]:
    return _all_skill_names()


@pytest.fixture(scope="module")
def known_agent_names() -> set[str]:
    return _all_agent_names()


def test_skill_tool_refs_resolve(known_skill_names):
    """Every Skill(x) in a SKILL.md allowed-tools must reference a real skill name."""
    errors = []
    for skill_dir in SKILLS_DIR.iterdir():
        skill_md = skill_dir / "SKILL.md"
        if not (skill_dir.is_dir() and skill_md.exists()):
            continue
        post = frontmatter.load(str(skill_md))
        allowed_tools = post.metadata.get("allowed-tools", "") or ""
        refs = _extract_skill_refs(str(allowed_tools))
        for ref in refs:
            if ref not in known_skill_names:
                errors.append(f"{skill_dir.name}/SKILL.md: Skill({ref}) not found")
    assert not errors, "Unresolved Skill() references in skill frontmatter:\n" + "\n".join(errors)


def test_agent_tool_refs_resolve(known_skill_names):
    """Every Skill(x) in an agent's tools field must reference a real skill name."""
    errors = []
    for agent_file in AGENTS_DIR.rglob("*.md"):
        post = frontmatter.load(str(agent_file))
        tools = post.metadata.get("tools", "") or ""
        refs = _extract_skill_refs(str(tools))
        for ref in refs:
            if ref not in known_skill_names:
                errors.append(f"{agent_file.name}: Skill({ref}) not found")
    assert not errors, "Unresolved Skill() references in agent frontmatter:\n" + "\n".join(errors)


def test_skill_body_skill_refs_resolve(known_skill_names):
    """Every Skill(x) mentioned in a SKILL.md body must reference a real skill name."""
    errors = []
    for skill_dir in SKILLS_DIR.iterdir():
        skill_md = skill_dir / "SKILL.md"
        if not (skill_dir.is_dir() and skill_md.exists()):
            continue
        post = frontmatter.load(str(skill_md))
        refs = _extract_skill_refs(post.content)
        for ref in refs:
            if ref not in known_skill_names:
                errors.append(f"{skill_dir.name}/SKILL.md body: Skill({ref}) not found")
    assert not errors, "Unresolved Skill() references in skill bodies:\n" + "\n".join(errors)

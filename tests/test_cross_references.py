import re

import frontmatter
import pytest

from paths import PLUGIN_DIRS, all_agent_files, all_skill_dirs

SKILL_REF_RE = re.compile(r"Skill\(([^)]+)\)")


def _extract_skill_refs(value: str) -> list[str]:
    return SKILL_REF_RE.findall(value)


def _all_skill_names() -> set[str]:
    """Known skill references: bare names and plugin-qualified names."""
    names = set()
    for plugin_dir in PLUGIN_DIRS:
        for skill_dir in (plugin_dir / "skills").glob("*"):
            skill_md = skill_dir / "SKILL.md"
            if skill_dir.is_dir() and skill_md.exists():
                post = frontmatter.load(str(skill_md))
                if "name" in post.metadata:
                    names.add(post.metadata["name"])
                    names.add(f"{plugin_dir.name}:{post.metadata['name']}")
    return names


@pytest.fixture(scope="module")
def known_skill_names() -> set[str]:
    return _all_skill_names()


def test_skill_tool_refs_resolve(known_skill_names):
    """Every Skill(x) in a SKILL.md allowed-tools must reference a real skill name."""
    errors = []
    for skill_dir in all_skill_dirs():
        post = frontmatter.load(str(skill_dir / "SKILL.md"))
        allowed_tools = post.metadata.get("allowed-tools", "") or ""
        for ref in _extract_skill_refs(str(allowed_tools)):
            if ref not in known_skill_names:
                errors.append(f"{skill_dir.name}/SKILL.md: Skill({ref}) not found")
    assert not errors, "Unresolved Skill() references in skill frontmatter:\n" + "\n".join(errors)


def test_agent_tool_refs_resolve(known_skill_names):
    """Every Skill(x) in an agent's tools field must reference a real skill name."""
    errors = []
    for agent_file in all_agent_files():
        post = frontmatter.load(str(agent_file))
        tools = post.metadata.get("tools", "") or ""
        for ref in _extract_skill_refs(str(tools)):
            if ref not in known_skill_names:
                errors.append(f"{agent_file.name}: Skill({ref}) not found")
    assert not errors, "Unresolved Skill() references in agent frontmatter:\n" + "\n".join(errors)


def test_skill_body_skill_refs_resolve(known_skill_names):
    """Every Skill(x) mentioned in a SKILL.md body must reference a real skill name."""
    errors = []
    for skill_dir in all_skill_dirs():
        post = frontmatter.load(str(skill_dir / "SKILL.md"))
        for ref in _extract_skill_refs(post.content):
            if ref not in known_skill_names:
                errors.append(f"{skill_dir.name}/SKILL.md body: Skill({ref}) not found")
    assert not errors, "Unresolved Skill() references in skill bodies:\n" + "\n".join(errors)

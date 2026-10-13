"""Selected skills require explicit invocation in each generated harness."""

import json
from pathlib import Path

import frontmatter
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SELECTED_SKILLS = {
    "authoring-tools": {"creating-skills", "creating-agents"},
    "engineering-workflow": {"planning", "researching"},
}


@pytest.mark.parametrize("harness", ["claude", "copilot", "codex"])
def test_invocation_policy_matches_supported_skills(harness):
    plugins_dir = ROOT / "dist" / harness / "plugins"
    selected = set()
    for skill_md in sorted(plugins_dir.glob("*/skills/*/SKILL.md")):
        plugin = skill_md.parents[2].name
        name = skill_md.parent.name
        post = frontmatter.load(str(skill_md))
        is_selected = name in SELECTED_SKILLS.get(plugin, set())
        sidecar = skill_md.parent / "agents" / "openai.yaml"
        if is_selected:
            selected.add(name)
        if harness in {"claude", "copilot"}:
            if is_selected:
                assert post.metadata["disable-model-invocation"] is True
                assert post.metadata.get("user-invocable", True) is True
            else:
                assert "disable-model-invocation" not in post.metadata
            assert not sidecar.exists()
            assert not (skill_md.parent / "agents").exists()
        else:
            assert "disable-model-invocation" not in post.metadata
            assert "user-invocable" not in post.metadata
            if is_selected:
                assert yaml.safe_load(sidecar.read_text()) == {
                    "policy": {"allow_implicit_invocation": False}
                }
            else:
                assert not sidecar.exists()
    assert selected == {"planning", "researching", "creating-skills", "creating-agents"}


@pytest.mark.parametrize("plugin_name", sorted(SELECTED_SKILLS))
def test_shared_copilot_registry_routes_to_flagged_skills(plugin_name):
    registry = json.loads((ROOT / ".github/plugin/marketplace.json").read_text())
    plugin = next(p for p in registry["plugins"] if p["name"] == plugin_name)
    assert plugin["source"] == f"dist/copilot/plugins/{plugin_name}"
    for name in SELECTED_SKILLS[plugin_name]:
        skill_md = ROOT / plugin["source"] / "skills" / name / "SKILL.md"
        assert frontmatter.load(str(skill_md)).metadata["disable-model-invocation"] is True


@pytest.mark.parametrize(
    ("harness", "command"),
    [
        ("claude", "/engineering-workflow:planning"),
        ("copilot", "/planning"),
        ("codex", "$planning"),
    ],
)
def test_researching_handoff_requires_user_invocation(harness, command):
    skill_md = (
        ROOT / "dist" / harness / "plugins" / "engineering-workflow"
        / "skills" / "researching" / "SKILL.md"
    )
    post = frontmatter.load(str(skill_md))
    assert f"`{command} docs/features/<NNN>-<feature-slug>`" in post.content
    assert "Do not invoke planning automatically" in post.content
    assert "You MUST use this skill before" not in post.metadata["description"]
    assert "Then invoke" not in post.content

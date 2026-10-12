"""Contracts for the verification workflows in every generated harness."""

import json
import re
from pathlib import Path

import frontmatter
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/plugins/authoring-tools"
SKILLS = ("create-verification-skill", "maintain-verification-skill")
PROJECT_DIRS = {
    "claude": ".claude/skills",
    "copilot": ".github/skills",
    "codex": ".agents/skills",
}
REGISTRIES = {
    "claude": ".claude-plugin/marketplace.json",
    "copilot": ".github/plugin/marketplace.json",
    "codex": ".agents/plugins/marketplace.json",
}
MANIFESTS = {
    "claude": ".claude-plugin/plugin.json",
    "copilot": "plugin.json",
    "codex": ".codex-plugin/plugin.json",
}
LOCAL_LINK_RE = re.compile(r"\[[^\]]+\]\((\./[^)]+)\)")


@pytest.fixture(params=PROJECT_DIRS)
def harness(request):
    return request.param


@pytest.fixture
def plugin_dir(harness):
    return ROOT / "dist" / harness / "plugins/authoring-tools"


@pytest.mark.parametrize("name", SKILLS)
def test_rendered_workflow_metadata_and_invocation(harness, plugin_dir, name):
    skill_md = plugin_dir / "skills" / name / "SKILL.md"
    post = frontmatter.load(str(skill_md))
    assert post.metadata["name"] == name
    assert 0 < len(post.metadata["description"]) <= 1024
    assert "targets" not in post.metadata
    assert len(skill_md.read_text().splitlines()) <= 500
    assert "{{" not in post.content and "{%" not in post.content
    assert ".cursor/" not in post.content
    command = f"${name}" if harness == "codex" else f"/authoring-tools:{name}"
    assert f"Invoke explicitly with `{command}`" in post.content


def test_registry_routes_to_versioned_authoring_plugin(harness, plugin_dir):
    registry = json.loads((ROOT / REGISTRIES[harness]).read_text())
    matches = [p for p in registry["plugins"] if p["name"] == "authoring-tools"]
    assert len(matches) == 1
    entry = matches[0]
    source = entry["source"]["path"] if harness == "codex" else entry["source"]
    assert (ROOT / source).resolve() == plugin_dir.resolve()
    manifest = json.loads((plugin_dir / MANIFESTS[harness]).read_text())
    version = yaml.safe_load((SOURCE / "plugin.yaml").read_text())["version"]
    assert manifest["version"] == version
    if harness != "codex":
        assert entry["version"] == version


def test_creator_uses_active_project_directory(harness, plugin_dir):
    body = frontmatter.load(str(
        plugin_dir / "skills/create-verification-skill/SKILL.md"
    )).content
    expected = PROJECT_DIRS[harness]
    assert f"at `{expected}/verify-<app>/`" in body
    assert f"Write `{expected}/verify-<app>/SKILL.md`" in body
    assert f"Create `{expected}/verify-<app>/features/README.md`" in body
    assert "relative to that project, not this installed plugin" in body
    assert "Never silently overwrite a skill or create a competing copy" in body
    assert "Normal verification skills remain eligible for automatic discovery" in body
    for section in ("Launch", "Doctor", "Drive", "Evidence", "Cleanup", "Helpers"):
        assert f"**{section}:**" in body
    assert "drive one mapped feature, capture evidence, and clean up" in body
    assert "After cleanup, confirm the evidence still exists" in body


def test_maintainer_preserves_discovery_coverage_and_shipping_contract(plugin_dir):
    body = frontmatter.load(str(
        plugin_dir / "skills/maintain-verification-skill/SKILL.md"
    )).content
    for project_dir in PROJECT_DIRS.values():
        assert f"`{project_dir}/`" in body
    for contract in (
        "deduplicate candidates pointing to the same physical directory",
        "Never edit product code during maintenance",
        "read the source directly with the same coverage",
        "Readers never drive the app and never edit files",
        "Exercise every mapped feature at least once",
        "cover its documented user entry points",
        "after every failed drive",
        "after every cleanup",
        "Re-drive every harness fix live before shipping",
        "if it prevents required coverage, report `blocked`",
        "Do not publish partial corrections",
        "Stage explicit file paths only",
        "Confirm the remote PR exists and includes the correction commit",
        "Never blindly retry PR creation",
    ):
        assert contract in body
    for outcome in ("clean", "changed", "blocked"):
        assert f"**{outcome}**:" in body
    assert "git-commits" in body


@pytest.mark.parametrize("name", SKILLS)
def test_bundled_license_and_relative_links(plugin_dir, name):
    skill_dir = plugin_dir / "skills" / name
    license_text = (skill_dir / "LICENSE").read_text()
    assert license_text == (SOURCE / "skills" / name / "LICENSE").read_text()
    assert "Copyright (c) 2026 Lauren Tan" in license_text
    assert "The above copyright notice and this permission notice" in license_text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in license_text
    body = frontmatter.load(str(skill_dir / "SKILL.md")).content
    assert "1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def" in body
    for relative in LOCAL_LINK_RE.findall(body):
        assert (skill_dir / relative).is_file(), relative


def test_feature_map_examples_are_complete_and_linked(plugin_dir):
    relative = Path("skills/create-verification-skill/references/feature-map-example")
    examples = plugin_dir / relative
    assert {p.name for p in examples.iterdir()} == {
        "README.md", "create-note.md", "search.md",
    }
    index = (examples / "README.md").read_text()
    assert set(LOCAL_LINK_RE.findall(index)) == {"./create-note.md", "./search.md"}
    for name in ("README.md", "create-note.md", "search.md"):
        content = (examples / name).read_text()
        assert content == (SOURCE / relative / name).read_text()
        if name == "README.md":
            continue
        assert content.startswith("# ")
        assert re.findall(r"^## (.+)$", content, re.MULTILINE) == [
            "Sub-features",
            "How to get to it (user POV)",
            "Driving it with control-notes",
            "Gotchas",
        ]
        assert "Preconditions:" in content
        assert (examples / name).is_file()

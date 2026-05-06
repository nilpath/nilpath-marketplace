import re
from pathlib import Path

import frontmatter
import pytest
from paths import SKILLS_DIR

KNOWN_MODELS = {"haiku", "sonnet", "opus"}
KNOWN_SUBDIRS = {"references", "templates", "workflows", "scripts", "examples", "prompts"}
KEBAB_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


def _skill_ids(skill_dirs):
    return [d.name for d in skill_dirs]


def pytest_generate_tests(metafunc):
    if "skill_dir" in metafunc.fixturenames:
        skill_dirs = sorted(
            p for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").exists()
        )
        metafunc.parametrize("skill_dir", skill_dirs, ids=[d.name for d in skill_dirs])


def test_skill_md_exists(skill_dir):
    assert (skill_dir / "SKILL.md").exists()


def test_skill_frontmatter_is_valid(skill_dir):
    post = frontmatter.load(str(skill_dir / "SKILL.md"))
    assert isinstance(post.metadata, dict), "Frontmatter must parse to a dict"


def test_skill_has_required_fields(skill_dir):
    post = frontmatter.load(str(skill_dir / "SKILL.md"))
    fm = post.metadata
    assert "name" in fm, "Missing required field: name"
    assert "description" in fm, "Missing required field: description"
    assert fm["name"], "name must not be empty"
    assert fm["description"], "description must not be empty"


def test_skill_name_is_kebab_case(skill_dir):
    post = frontmatter.load(str(skill_dir / "SKILL.md"))
    name = post.metadata.get("name", "")
    assert KEBAB_RE.match(name), f"name '{name}' is not kebab-case"
    assert len(name) <= 64, f"name '{name}' exceeds 64 characters"


def test_skill_model_field_if_present(skill_dir):
    post = frontmatter.load(str(skill_dir / "SKILL.md"))
    model = post.metadata.get("model")
    if model is not None:
        assert model in KNOWN_MODELS, f"model '{model}' is not one of {KNOWN_MODELS}"


def test_skill_line_count(skill_dir):
    lines = (skill_dir / "SKILL.md").read_text().splitlines()
    assert len(lines) <= 500, f"SKILL.md has {len(lines)} lines (max 500)"


def test_skill_only_known_subdirs(skill_dir):
    for child in skill_dir.iterdir():
        if child.is_dir():
            assert child.name in KNOWN_SUBDIRS, (
                f"Unknown subdirectory '{child.name}' in skill '{skill_dir.name}'"
            )

from pathlib import Path
import frontmatter
import pytest
from paths import AGENTS_DIR

KNOWN_MODELS = {"haiku", "sonnet", "opus"}


def pytest_generate_tests(metafunc):
    if "agent_file" in metafunc.fixturenames:
        agent_files = sorted(AGENTS_DIR.rglob("*.md"))
        metafunc.parametrize("agent_file", agent_files, ids=[f.stem for f in agent_files])


def test_agent_frontmatter_is_valid(agent_file):
    post = frontmatter.load(str(agent_file))
    assert isinstance(post.metadata, dict), "Frontmatter must parse to a dict"


def test_agent_has_required_fields(agent_file):
    post = frontmatter.load(str(agent_file))
    fm = post.metadata
    assert "name" in fm, "Missing required field: name"
    assert "description" in fm, "Missing required field: description"
    assert fm["name"], "name must not be empty"
    assert fm["description"], "description must not be empty"


def test_agent_model_field_if_present(agent_file):
    post = frontmatter.load(str(agent_file))
    model = post.metadata.get("model")
    if model is not None:
        assert model in KNOWN_MODELS, f"model '{model}' is not one of {KNOWN_MODELS}"


def test_agent_has_non_empty_body(agent_file):
    post = frontmatter.load(str(agent_file))
    assert post.content.strip(), "Agent file has an empty body (system prompt is missing)"



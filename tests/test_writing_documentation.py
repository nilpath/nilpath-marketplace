"""Tests specific to the writing-documentation skill and its agents.

These tests cover design invariants not caught by the generic structure tests:
- doc-auditor must be read-only (permissionMode + disallowedTools)
- writing-documentation must be able to spawn agents (Agent in allowed-tools)
- agents are filed under the correct category directories
"""

import frontmatter
from paths import AGENTS_DIR, SKILLS_DIR

DOC_AUDITOR = AGENTS_DIR / "review" / "doc-auditor.md"
DOC_WRITER = AGENTS_DIR / "implementation" / "doc-writer.md"
WRITING_DOC_SKILL = SKILLS_DIR / "writing-documentation" / "SKILL.md"


def test_doc_auditor_in_review_category():
    """doc-auditor.md must live under agents/review/ (not implementation or research)."""
    assert DOC_AUDITOR.exists(), "agents/review/doc-auditor.md not found"


def test_doc_writer_in_implementation_category():
    """doc-writer.md must live under agents/implementation/ (not review or research)."""
    assert DOC_WRITER.exists(), "agents/implementation/doc-writer.md not found"


def test_doc_auditor_permission_mode():
    """doc-auditor must declare permissionMode: plan to enforce read-only access."""
    post = frontmatter.load(str(DOC_AUDITOR))
    assert post.metadata.get("permissionMode") == "plan", (
        "doc-auditor must have 'permissionMode: plan' to prevent file edits"
    )


def test_doc_auditor_disallowed_tools():
    """doc-auditor must disallow Write and Edit to enforce read-only at harness level."""
    post = frontmatter.load(str(DOC_AUDITOR))
    raw = post.metadata.get("disallowedTools", "")
    # disallowedTools may be a YAML list or a comma-separated string
    if isinstance(raw, list):
        tools = raw
    else:
        tools = [t.strip() for t in str(raw).split(",")]
    assert "Write" in tools, "doc-auditor disallowedTools must include 'Write'"
    assert "Edit" in tools, "doc-auditor disallowedTools must include 'Edit'"


def test_writing_documentation_allows_agent_tool():
    """writing-documentation must include Agent in allowed-tools to delegate to workers."""
    post = frontmatter.load(str(WRITING_DOC_SKILL))
    raw = post.metadata.get("allowed-tools", "")
    # allowed-tools may be a YAML list or a space/comma-separated string
    if isinstance(raw, list):
        tools_str = " ".join(raw)
    else:
        tools_str = str(raw)
    assert "Agent" in tools_str, (
        "writing-documentation allowed-tools must include 'Agent' "
        "(required to spawn doc-writer and doc-auditor)"
    )

"""Unit tests for the buildkit translation core."""

from pathlib import Path

import pytest

from buildkit.config import load_config
from buildkit.fm import FrontmatterError, dump_frontmatter, process_frontmatter, split_document
from buildkit.toolmap import parse_entry, resolve_model_tier, split_tool_list, translate_tools

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def cfg():
    return load_config(REPO_ROOT)


class TestParsing:
    def test_plain_tool(self):
        entry = parse_entry("file-read")
        assert (entry.name, entry.scope, entry.passthrough_harness) == ("file-read", None, None)

    def test_scoped_tool(self):
        entry = parse_entry("shell(git add:*)")
        assert (entry.name, entry.scope) == ("shell", "git add:*")

    def test_passthrough(self):
        entry = parse_entry("claude:mcp__context7__query-docs")
        assert entry.passthrough_harness == "claude"
        assert entry.name == "mcp__context7__query-docs"

    def test_split_comma_with_scoped_spaces(self):
        parts = split_tool_list("shell(git add :*), file-read, subagent(x)")
        assert parts == ["shell(git add :*)", "file-read", "subagent(x)"]

    def test_split_space_separated(self):
        parts = split_tool_list("ask-user shell(git diff*) subagent(code-reviewer)")
        assert parts == ["ask-user", "shell(git diff*)", "subagent(code-reviewer)"]

    def test_split_skips_empty_entries(self):
        assert split_tool_list("file-read, , todo") == ["file-read", "todo"]

    def test_split_accepts_lists(self):
        assert split_tool_list(["file-read", "todo"]) == ["file-read", "todo"]


class TestTranslation:
    def test_claude_keeps_scopes(self, cfg):
        out, warnings = translate_tools(
            ["shell(git:*)", "file-read", "subagent(Explore)"], cfg.harnesses["claude"], cfg
        )
        assert out == ["Bash(git:*)", "Read", "Agent(Explore)"]
        assert warnings == []

    def test_copilot_collapses_and_dedupes(self, cfg):
        out, warnings = translate_tools(
            ["glob-search", "content-search", "shell(git:*)", "ask-user"],
            cfg.harnesses["copilot"],
            cfg,
        )
        assert out == ["search", "execute"]
        assert any("ask-user" in w for w in warnings)

    def test_codex_strips_silently(self, cfg):
        out, warnings = translate_tools(["shell", "file-read"], cfg.harnesses["codex"], cfg)
        assert out == []
        assert warnings == []

    def test_passthrough_only_on_matching_harness(self, cfg):
        entries = ["claude:mcp__x__y"]
        claude_out, _ = translate_tools(entries, cfg.harnesses["claude"], cfg)
        copilot_out, copilot_warnings = translate_tools(entries, cfg.harnesses["copilot"], cfg)
        assert claude_out == ["mcp__x__y"]
        assert copilot_out == [] and copilot_warnings == []

    def test_unknown_canonical_tool_raises(self, cfg):
        with pytest.raises(ValueError, match="unknown canonical tool"):
            translate_tools(["Bash"], cfg.harnesses["claude"], cfg)


class TestModels:
    def test_direct_mapping(self, cfg):
        resolved, warnings = resolve_model_tier("medium", cfg.harnesses["claude"], cfg)
        assert resolved == "sonnet" and warnings == []

    def test_nearest_neighbour_fallback(self, cfg):
        harness = cfg.harnesses["claude"]
        original = harness.raw["models"]["map"]
        harness.raw["models"]["map"] = {"small": "haiku", "large": "opus"}
        try:
            resolved, warnings = resolve_model_tier("medium", harness, cfg)
            assert resolved == "haiku"  # ties resolve to the lower tier
            assert warnings
        finally:
            harness.raw["models"]["map"] = original

    def test_unknown_tier_errors(self, cfg):
        resolved, warnings = resolve_model_tier("gigantic", cfg.harnesses["claude"], cfg)
        assert resolved is None
        assert any("unknown model tier" in w for w in warnings)


class TestFrontmatter:
    def test_split_document(self):
        data, body = split_document("---\nname: x\ndescription: y\n---\nbody\n")
        assert data == {"name": "x", "description": "y"}
        assert body == "body\n"

    def test_build_only_keys_stripped(self, cfg):
        data = {"name": "x", "description": "y", "targets": ["claude"], "tools": ["file-read"]}
        out, _ = process_frontmatter(data, "skill", cfg.harnesses["claude"], cfg, "skill/x")
        assert "targets" not in out
        assert out["allowed-tools"] == "Read"

    def test_copilot_skill_drops_tools_key(self, cfg):
        data = {"name": "x", "description": "y", "targets": ["copilot"], "tools": ["file-read"]}
        out, _ = process_frontmatter(data, "skill", cfg.harnesses["copilot"], cfg, "skill/x")
        assert "tools" not in out and "allowed-tools" not in out

    def test_reasoning_mapped_for_claude_dropped_for_copilot(self, cfg):
        data = {"name": "x", "description": "y", "targets": ["claude"], "reasoning": "max"}
        out, _ = process_frontmatter(data, "agent", cfg.harnesses["claude"], cfg, "agent/x")
        assert out["effort"] == "max"
        out, warnings = process_frontmatter(
            {"name": "x", "description": "y", "reasoning": "high"},
            "agent", cfg.harnesses["copilot"], cfg, "agent/x",
        )
        assert "reasoning" not in out
        assert any("reasoning" in w for w in warnings)

    def test_disallowed_key_raises(self, cfg):
        data = {"name": "x", "description": "y", "bogus-key": 1}
        with pytest.raises(FrontmatterError, match="bogus-key"):
            process_frontmatter(data, "skill", cfg.harnesses["claude"], cfg, "skill/x")

    def test_dump_round_trip_style(self):
        text = dump_frontmatter({"name": "x", "description": "a: b", "tools": ["Read", "Write"]})
        assert text.startswith("---\n")
        assert "description: 'a: b'" in text
        assert "  - Read" in text

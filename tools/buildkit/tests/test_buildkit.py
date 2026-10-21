"""Unit tests for the buildkit translation core."""

from copy import deepcopy
from pathlib import Path

import pytest

from buildkit.build import BuildResult, _build_hooks, _build_skill, build
from buildkit.config import HarnessConfig, PluginConfig, load_config
from buildkit.fm import (
    FrontmatterError,
    dump_agent_toml,
    dump_frontmatter,
    process_frontmatter,
    split_document,
)
from buildkit.toolmap import parse_entry, resolve_model_tier, split_tool_list, translate_tools
from buildkit.render import make_environment

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
            ["shell(git:*)", "file-read", "subagent(Explore)"], cfg.harnesses["claude"], cfg, "skill"
        )
        assert out == ["Bash(git:*)", "Read", "Agent(Explore)"]
        assert warnings == []

    def test_copilot_collapses_and_dedupes(self, cfg):
        out, warnings = translate_tools(
            ["glob-search", "content-search", "shell(git:*)", "ask-user"],
            cfg.harnesses["copilot"],
            cfg,
            "agent",
        )
        assert out == ["search", "execute"]
        assert any("ask-user" in w for w in warnings)

    def test_copilot_agent_aliases_remain_available(self, cfg):
        out, warnings = translate_tools(
            ["shell", "file-read", "file-write", "glob-search", "subagent(x)", "web-fetch"],
            cfg.harnesses["copilot"], cfg, "agent",
        )
        assert out == ["execute", "read", "edit", "search", "agent", "web"]
        assert warnings == []

    def test_codex_strips_silently(self, cfg):
        out, warnings = translate_tools(["shell", "file-read"], cfg.harnesses["codex"], cfg, "skill")
        assert out == []
        assert warnings == []

    def test_passthrough_only_on_matching_harness(self, cfg):
        entries = ["claude:mcp__x__y"]
        claude_out, _ = translate_tools(entries, cfg.harnesses["claude"], cfg, "skill")
        copilot_out, copilot_warnings = translate_tools(entries, cfg.harnesses["copilot"], cfg, "skill")
        assert claude_out == ["mcp__x__y"]
        assert copilot_out == [] and copilot_warnings == []

    def test_unknown_canonical_tool_raises(self, cfg):
        with pytest.raises(ValueError, match="unknown canonical tool"):
            translate_tools(["Bash"], cfg.harnesses["claude"], cfg, "skill")

    @pytest.mark.parametrize("entry", ["shell()", "shell( )", "shell(git:*"])
    def test_malformed_scope_rejected(self, cfg, entry):
        with pytest.raises(ValueError, match="tool scope"):
            translate_tools([entry], cfg.harnesses["copilot"], cfg, "skill")

    def test_copilot_skill_preserves_scopes_and_excludes_bare_shell(self, cfg):
        out, warnings = translate_tools(
            ["shell", "shell(git:*)", 'shell(python3 "/installed path/helper.py":*)', "file-read"],
            cfg.harnesses["copilot"], cfg, "skill",
        )
        assert out == ["shell(git:*)", 'shell(python3 "/installed path/helper.py":*)']
        assert warnings == [
            "tool 'shell' requires a scope for copilot skill; dropped",
            "tool 'file-read' has no copilot equivalent; dropped",
        ]

    def test_skill_policy_replaces_every_agent_setting(self, cfg):
        harness = HarnessConfig("copilot", deepcopy(cfg.harnesses["copilot"].raw))
        harness.raw["frontmatter"]["skill"]["tools"] = {"map": {"shell": "shell"}}
        out, warnings = translate_tools(
            ["shell(git:*)", "shell(git:*)", "file-read"], harness, cfg, "skill"
        )
        assert out == ["shell", "shell"]
        assert warnings == ["tool 'file-read' not mapped for copilot; dropped"]
        harness.raw["frontmatter"]["skill"]["key_for_tools"] = "allowed-tools"
        harness.raw["frontmatter"]["skill"]["allowed"].append("allowed-tools")
        data, _ = process_frontmatter(
            {"name": "x", "description": "y", "tools": ["shell", "shell"]},
            "skill", harness, cfg, "skill/x",
        )
        assert data["allowed-tools"] == "shell, shell"
        data, _ = process_frontmatter(
            {"name": "x", "description": "y", "tools": ["shell", "shell"]},
            "agent", harness, cfg, "agent/x",
        )
        assert data["tools"] == ["execute"]

    @pytest.mark.parametrize("scope", ["./scripts/helper.sh:*", "git feature/branch:*"])
    def test_claude_does_not_reject_relative_paths_or_slashes(self, cfg, scope):
        out, warnings = translate_tools([f"shell({scope})"], cfg.harnesses["claude"], cfg, "skill")
        assert out == [f"Bash({scope})"]
        assert warnings == []


class TestSkillPermissionRendering:
    def test_dormant_copilot_policy_renders_scoped_list_without_agent_aliases(self, cfg, tmp_path):
        harness = HarnessConfig("copilot", deepcopy(cfg.harnesses["copilot"].raw))
        harness.raw["frontmatter"]["skill"]["key_for_tools"] = "allowed-tools"
        harness.raw["frontmatter"]["skill"]["allowed"].append("allowed-tools")
        skill_dir = tmp_path / "fixture"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md.j2").write_text(
            '---\nname: fixture\ndescription: Fixture.\ntargets: [copilot]\n'
            'tools:\n  - shell\n  - shell(git:*)\n'
            '  - \'shell(python3 "/installed path/helper.py":*)\'\n'
            '  - file-read\n---\nFixture.\n'
        )
        result = BuildResult()
        plugin = next(p for p in cfg.plugins if p.name == "git-tools")
        _build_skill(make_environment(), skill_dir, harness, plugin, cfg, tmp_path / "out", result)
        text = result.written[0].read_text()
        data, _ = split_document(text)
        assert data == {
            "name": "fixture", "description": "Fixture.",
            "allowed-tools": ["shell(git:*)", 'shell(python3 "/installed path/helper.py":*)'],
        }
        assert "\nallowed-tools:\n  - shell(git:*)\n" in text
        assert "execute" not in text and "\n  - shell\n" not in text
        assert result.warnings == [
            "git-tools/skill/fixture: tool 'shell' requires a scope for copilot skill; dropped",
            "git-tools/skill/fixture: tool 'file-read' has no copilot equivalent; dropped",
        ]

    def test_normal_build_retains_runtime_gates_and_agent_aliases(self, tmp_path):
        result = build(REPO_ROOT, out_root=tmp_path)
        for path in result.written:
            if path.name == "SKILL.md" and "copilot" in path.parts:
                data, _ = split_document(path.read_text())
                assert "tools" not in data and "allowed-tools" not in data
        agent = tmp_path / "dist/copilot/plugins/nstack/com.github.copilot/agents/nstack-agent.agent.md"
        data, _ = split_document(agent.read_text())
        assert data["tools"] == ["read", "edit", "execute", "search"]
        assert not any("copilot skill" in warning for warning in result.warnings)

    def test_copilot_raw_tools_are_rejected_and_canonical_tools_stay_gated(self, cfg, tmp_path):
        plugin = next(p for p in cfg.plugins if p.name == "git-tools")
        skill_dir = tmp_path / "fixture"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md.j2").write_text(
            "---\nname: fixture\ndescription: Fixture.\ntargets: [copilot]\n"
            "allowed-tools: shell\n---\nFixture.\n"
        )
        with pytest.raises(FrontmatterError, match="allowed-tools"):
            _build_skill(
                make_environment(), skill_dir, cfg.harnesses["copilot"], plugin, cfg,
                tmp_path / "out", BuildResult(),
            )
        (skill_dir / "SKILL.md.j2").write_text(
            "---\nname: fixture\ndescription: Fixture.\ntargets: [copilot]\n"
            "tools:\n  - shell(git:*)\n---\nFixture.\n"
        )
        result = BuildResult()
        _build_skill(
            make_environment(), skill_dir, cfg.harnesses["copilot"], plugin, cfg,
            tmp_path / "out", result,
        )
        data, _ = split_document(result.written[0].read_text())
        assert "tools" not in data and "allowed-tools" not in data
        assert result.warnings == []

    @pytest.mark.parametrize(
        ("plugin_name", "skill_name", "expected_tools", "scripts"),
        [
            (
                "git-tools", "gh-pr-review",
                'Bash(gh:*), Bash(git remote:*), '
                'Bash("${CLAUDE_PLUGIN_ROOT}/skills/gh-pr-review/scripts/pr-info.sh":*), '
                'Bash("${CLAUDE_PLUGIN_ROOT}/skills/gh-pr-review/scripts/create-review.sh":*), '
                'Bash("${CLAUDE_PLUGIN_ROOT}/skills/gh-pr-review/scripts/submit-review.sh":*), Read',
                ["pr-info.sh", "create-review.sh", "submit-review.sh"],
            ),
            (
                "git-tools", "git-stacked-prs",
                'Bash(git:*), '
                'Bash("${CLAUDE_PLUGIN_ROOT}/skills/git-stacked-prs/scripts/stack-rebase.sh":*), '
                'Bash("${CLAUDE_PLUGIN_ROOT}/skills/git-stacked-prs/scripts/stack-status.sh":*), '
                'Bash("${CLAUDE_PLUGIN_ROOT}/skills/git-stacked-prs/scripts/update-pr-targets.sh":*), '
                'Bash("${CLAUDE_PLUGIN_ROOT}/skills/git-stacked-prs/scripts/stack-backup.sh":*), '
                'Read, Edit, Write',
                ["stack-rebase.sh", "stack-status.sh", "update-pr-targets.sh", "stack-backup.sh"],
            ),
            (
                "nstack", "show-me-your-work",
                'Bash("${CLAUDE_PLUGIN_ROOT}/skills/show-me-your-work/scripts/log.sh":*)',
                ["log.sh"],
            ),
        ],
    )
    def test_claude_script_callers_match_literal_rules(
        self, cfg, tmp_path, plugin_name, skill_name, expected_tools, scripts
    ):
        plugin = next(p for p in cfg.plugins if p.name == plugin_name)
        result = BuildResult()
        _build_skill(
            make_environment(), plugin.src_dir / "skills" / skill_name,
            cfg.harnesses["claude"], plugin, cfg, tmp_path, result,
        )
        data, body = split_document(result.written[0].read_text())
        assert data["allowed-tools"] == expected_tools
        assert "PR_INFO=$(" not in body
        for script in scripts:
            assert f'"${{CLAUDE_PLUGIN_ROOT}}/skills/{skill_name}/scripts/{script}"' in body
            assert (result.written[0].parent / "scripts" / script).stat().st_mode & 0o111

    @pytest.mark.parametrize("harness_id", ["claude", "codex"])
    def test_normal_skill_build_preserves_claude_and_strips_codex(self, cfg, tmp_path, harness_id):
        plugin = next(p for p in cfg.plugins if p.name == "git-tools")
        harness = cfg.harnesses[harness_id]
        result = BuildResult()
        _build_skill(
            make_environment(), plugin.src_dir / "skills/gh-address-comments",
            harness, plugin, cfg, tmp_path, result,
        )
        data, body = split_document(result.written[0].read_text())
        if harness_id == "claude":
            assert data["allowed-tools"] == (
                'Bash(gh:*), Bash(jq:*), '
                'Bash("${CLAUDE_PLUGIN_ROOT}/skills/gh-address-comments/scripts/fetch-comments.sh":*), '
                'Bash("${CLAUDE_PLUGIN_ROOT}/skills/gh-address-comments/scripts/reply-to-thread.sh":*), '
                'Read, Write, Edit'
            )
            assert '"${CLAUDE_PLUGIN_ROOT}/skills/gh-address-comments/scripts/fetch-comments.sh" 123' in body
            assert "COMMENTS=$(" not in body
        else:
            assert "allowed-tools" not in data and "tools" not in data
            assert '"<gh-address-comments skill directory>/scripts/fetch-comments.sh" 123' in body


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
    @pytest.mark.parametrize("harness_id", ["claude", "copilot"])
    def test_manual_only_skill_flag_preserved(self, cfg, harness_id):
        data = {"name": "x", "description": "y", "disable-model-invocation": True}
        out, warnings = process_frontmatter(
            data, "skill", cfg.harnesses[harness_id], cfg, "skill/x"
        )
        assert out["disable-model-invocation"] is True
        assert warnings == []

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
        data = {
            "name": "x", "description": "y", "targets": ["copilot"],
            "tools": ["shell", "shell(git:*)", "file-read"],
        }
        out, warnings = process_frontmatter(
            data, "skill", cfg.harnesses["copilot"], cfg, "skill/x"
        )
        assert "tools" not in out and "allowed-tools" not in out
        assert warnings == []

        harness = HarnessConfig("copilot", deepcopy(cfg.harnesses["copilot"].raw))
        harness.raw["frontmatter"]["skill"]["key_for_tools"] = "allowed-tools"
        harness.raw["frontmatter"]["skill"]["allowed"].append("allowed-tools")
        out, warnings = process_frontmatter(data, "skill", harness, cfg, "skill/x")
        assert out["allowed-tools"] == ["shell(git:*)"]
        assert warnings == [
            "skill/x: tool 'shell' requires a scope for copilot skill; dropped",
            "skill/x: tool 'file-read' has no copilot equivalent; dropped",
        ]

    def test_active_copilot_skill_warns_when_all_tools_drop(self, cfg):
        harness = HarnessConfig("copilot", deepcopy(cfg.harnesses["copilot"].raw))
        harness.raw["frontmatter"]["skill"]["key_for_tools"] = "allowed-tools"
        harness.raw["frontmatter"]["skill"]["allowed"].append("allowed-tools")
        out, warnings = process_frontmatter(
            {"name": "x", "description": "y", "tools": ["shell", "file-read"]},
            "skill", harness, cfg, "skill/x",
        )
        assert "allowed-tools" not in out
        assert warnings == [
            "skill/x: tool 'shell' requires a scope for copilot skill; dropped",
            "skill/x: tool 'file-read' has no copilot equivalent; dropped",
        ]

    @pytest.mark.parametrize("tools", [["unknown"], ["shell()"], ["shell( )"]])
    def test_gated_copilot_skill_tools_still_validate(self, cfg, tools):
        data = {"name": "x", "description": "y", "tools": tools}
        with pytest.raises(ValueError):
            process_frontmatter(data, "skill", cfg.harnesses["copilot"], cfg, "skill/x")

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


class TestCodexAgents:
    def test_permission_mode_translates_to_sandbox(self, cfg):
        data = {"name": "x", "description": "y", "permissionMode": "plan"}
        out, warnings = process_frontmatter(data, "agent", cfg.harnesses["codex"], cfg, "agent/x")
        assert out["sandbox_mode"] == "read-only"
        assert "permissionMode" not in out

    def test_unmapped_permission_mode_dropped_with_warning(self, cfg):
        data = {"name": "x", "description": "y", "permissionMode": "acceptEdits"}
        out, warnings = process_frontmatter(data, "agent", cfg.harnesses["codex"], cfg, "agent/x")
        assert "sandbox_mode" not in out
        assert any("permissionMode" in w for w in warnings)

    def test_dump_agent_toml_round_trips(self):
        import tomllib

        text, warnings = dump_agent_toml(
            {"name": "x", "description": 'says "hi" \\ there', "model": "gpt-5.1-codex"},
            "# Title\n\nDo the thing.\n",
        )
        parsed = tomllib.loads(text)
        assert parsed["description"] == 'says "hi" \\ there'
        assert parsed["developer_instructions"] == "# Title\n\nDo the thing.\n"
        assert warnings == []

    def test_dump_agent_toml_defuses_triple_quotes(self):
        import tomllib

        text, warnings = dump_agent_toml({"name": "x", "description": "y"}, "code: '''py'''\n")
        parsed = tomllib.loads(text)
        assert "'''" not in parsed["developer_instructions"]
        assert warnings


class TestProseHelpers:
    TEMPLATE = (
        "Delegate to {{ spawn('engineering-workflow:review:code-reviewer') }}, "
        "commit via {{ skill_ref('git-tools:git-commits') }}, "
        "track with {{ todo }}, ask via {{ ask_user }}."
    )

    def _render(self, cfg, harness_id):
        from buildkit.render import make_environment, render_text

        return render_text(make_environment(), self.TEMPLATE, cfg.harnesses[harness_id], cfg)

    def test_claude_prose(self, cfg):
        out = self._render(cfg, "claude")
        assert 'Agent(subagent_type="engineering-workflow:review:code-reviewer")' in out
        assert "the `git-tools:git-commits` skill" in out
        assert "`TodoWrite`" in out and "`AskUserQuestion`" in out

    def test_copilot_prose(self, cfg):
        out = self._render(cfg, "copilot")
        assert "`code-reviewer` custom agent" in out
        assert "`git-commits` skill (`/git-commits`)" in out
        assert "todo list" in out and "chat question" in out

    def test_codex_prose(self, cfg):
        out = self._render(cfg, "codex")
        assert "`code-reviewer` agent (spawn it as a subagent)" in out
        assert "update_plan" in out

    @pytest.mark.parametrize(
        ("harness_id", "expected"),
        [
            ("claude", '`Agent(subagent_type="p:cat:agent")` with `[tag x]` at the start of `description`'),
            ("copilot", "agent type `p:agent`, `[tag x]` at the start of the description"),
            ("codex", "`spawn_agent` with `agent_type` `agent` and a `message` that starts with `[tag x]`"),
        ],
    )
    def test_launch_prose(self, cfg, harness_id, expected):
        from buildkit.render import make_environment, render_text

        out = render_text(
            make_environment(), "{{ launch('p:cat:agent', '[tag x]') }}", cfg.harnesses[harness_id], cfg
        )
        assert expected in out

    def test_missing_prose_key_fails_loudly(self, cfg):
        from buildkit.render import make_environment, render_text

        harness = cfg.harnesses["claude"]
        saved = harness.raw.pop("prose")
        try:
            with pytest.raises(KeyError):
                render_text(make_environment(), "{{ spawn('a:b:c') }}", harness, cfg)
        finally:
            harness.raw["prose"] = saved


class TestEmptyPluginTrees:
    def test_authoring_tools_only_in_claude_tree(self):
        import json

        assert (REPO_ROOT / "dist/claude/plugins/authoring-tools/skills").is_dir()
        assert not (REPO_ROOT / "dist/copilot/plugins/authoring-tools").exists()
        assert not (REPO_ROOT / "dist/codex/plugins/authoring-tools").exists()
        codex_registry = json.loads(
            (REPO_ROOT / ".agents/plugins/marketplace.json").read_text()
        )
        assert "authoring-tools" not in [p["name"] for p in codex_registry["plugins"]]
        copilot_registry = json.loads(
            (REPO_ROOT / ".github/plugin/marketplace.json").read_text()
        )
        assert "authoring-tools" not in [p["name"] for p in copilot_registry["plugins"]]
        claude_registry = json.loads(
            (REPO_ROOT / ".claude-plugin/marketplace.json").read_text()
        )
        assert "authoring-tools" in [p["name"] for p in claude_registry["plugins"]]


class TestConditionalSupportingFiles:
    @pytest.mark.parametrize("harness_id", ["claude", "copilot", "codex"])
    def test_empty_supporting_templates_omitted(self, cfg, tmp_path, harness_id):
        skill_dir = tmp_path / "src" / "conditional-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md.j2").write_text(
            "---\nname: conditional-skill\ndescription: Test conditional files.\n"
            "targets: [claude, copilot, codex]\n---\nBody\n"
        )
        (skill_dir / "agents").mkdir()
        (skill_dir / "agents" / "openai.yaml.j2").write_text(
            '{% if harness == "codex" %}\n'
            "policy:\n  allow_implicit_invocation: false\n"
            "{% endif %}\n"
        )
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "empty.md.j2").write_text(" \n\t\n")
        (skill_dir / "references" / "shared.md.j2").write_text("Harness: {{ harness }}\n")
        (skill_dir / "references" / "empty.txt").write_text("")
        plugin = next(p for p in cfg.plugins if p.name == "engineering-workflow")
        harness = cfg.harnesses[harness_id]
        result = BuildResult()
        out_root = tmp_path / "out"

        assert _build_skill(
            make_environment(), skill_dir, harness, plugin, cfg, out_root, result
        )

        out_dir = out_root / harness.dist_root / "plugins" / plugin.name / "skills" / skill_dir.name
        assert not (out_dir / "references" / "empty.md").exists()
        assert (out_dir / "references" / "empty.txt").read_text() == ""
        assert (out_dir / "references" / "shared.md").read_text() == f"Harness: {harness_id}\n"
        if harness_id == "codex":
            assert (out_dir / "agents" / "openai.yaml").read_text() == (
                "\npolicy:\n  allow_implicit_invocation: false\n\n"
            )
        else:
            assert not (out_dir / "agents").exists()
        assert all(path.is_file() for path in result.written)
        assert not any(path.name == "empty.md" for path in result.written)

    def test_empty_skill_entry_point_still_rejected(self, cfg, tmp_path):
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md.j2").write_text(" \n")
        plugin = next(p for p in cfg.plugins if p.name == "engineering-workflow")
        with pytest.raises(FrontmatterError, match="frontmatter"):
            _build_skill(
                make_environment(), skill_dir, cfg.harnesses["claude"], plugin, cfg,
                tmp_path / "out", BuildResult(),
            )


class TestPluginHooks:
    TEMPLATE = (
        '{% if harness == "copilot" %}{"version": 1, "hooks": {"preToolUse": []}}'
        '{% elif harness == "claude" %}{"hooks": {"PreToolUse": []}}{% endif %}\n'
    )

    def _plugin(self, tmp_path, template: str | None) -> PluginConfig:
        src = tmp_path / "src" / "hooked"
        (src / "hooks").mkdir(parents=True)
        if template is not None:
            (src / "hooks" / "hooks.json.j2").write_text(template)
        return PluginConfig(src_dir=src, meta={"name": "hooked", "version": "0.0.0"})

    @pytest.mark.parametrize(
        ("harness_id", "expected"),
        [
            ("claude", "hooks/hooks.json"),
            ("copilot", "com.github.copilot/hooks/hooks.json"),
            ("codex", None),
        ],
    )
    def test_renders_per_harness_and_skips_empty(self, cfg, tmp_path, harness_id, expected):
        import json

        plugin = self._plugin(tmp_path, self.TEMPLATE)
        harness = cfg.harnesses[harness_id]
        out_root = tmp_path / "out"
        result = BuildResult()
        written = _build_hooks(make_environment(), plugin, harness, cfg, out_root, result)
        plugin_dir = out_root / harness.dist_root / "plugins" / "hooked"
        if expected is None:
            assert written is False
            assert not plugin_dir.exists()
            assert result.written == []
        else:
            assert written is True
            assert json.loads((plugin_dir / expected).read_text())["hooks"]
            assert result.written == [plugin_dir / expected]

    def test_plugin_without_hooks_template_writes_nothing(self, cfg, tmp_path):
        plugin = self._plugin(tmp_path, None)
        assert not _build_hooks(
            make_environment(), plugin, cfg.harnesses["claude"], cfg, tmp_path / "out", BuildResult()
        )

    def test_invalid_json_fails_loudly(self, cfg, tmp_path):
        plugin = self._plugin(tmp_path, '{"hooks": [}\n')
        with pytest.raises(ValueError, match="not valid JSON"):
            _build_hooks(
                make_environment(), plugin, cfg.harnesses["codex"], cfg, tmp_path / "out", BuildResult()
            )


class TestPluginHookSupportFiles:
    @pytest.mark.parametrize(
        ("harness_id", "hooks_dir"),
        [("claude", "hooks"), ("copilot", "com.github.copilot/hooks"), ("codex", "hooks")],
    )
    def test_support_files_ship_next_to_the_hooks_file(self, cfg, tmp_path, harness_id, hooks_dir):
        src = tmp_path / "src" / "hooked"
        (src / "hooks" / "data").mkdir(parents=True)
        (src / "hooks" / "hooks.json.j2").write_text('{"hooks": {}}\n')
        script = src / "hooks" / "run.py"
        script.write_text("print('hi')\n")
        script.chmod(0o755)
        (src / "hooks" / "data" / "note.md").write_text("note\n")
        (src / "hooks" / "data" / "harness.txt.j2").write_text("{{ harness }}\n")
        (src / "hooks" / "data" / "empty.txt.j2").write_text("{% if false %}x{% endif %}\n")
        (src / "hooks" / "__pycache__").mkdir()
        (src / "hooks" / "__pycache__" / "run.cpython-311.pyc").write_bytes(b"x")
        plugin = PluginConfig(src_dir=src, meta={"name": "hooked", "version": "0.0.0"})
        harness = cfg.harnesses[harness_id]
        out_root = tmp_path / "out"

        assert _build_hooks(make_environment(), plugin, harness, cfg, out_root, BuildResult())

        out = out_root / harness.dist_root / "plugins" / "hooked" / hooks_dir
        assert (out / "run.py").read_text() == "print('hi')\n"
        assert (out / "run.py").stat().st_mode & 0o111
        assert (out / "data" / "note.md").read_text() == "note\n"
        assert (out / "data" / "harness.txt").read_text() == f"{harness_id}\n"
        assert not (out / "data" / "empty.txt").exists()
        assert not (out / "__pycache__").exists()
        assert not (out / "hooks.json.j2").exists()

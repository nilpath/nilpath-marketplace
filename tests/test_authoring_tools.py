"""Static authoring contracts; these do not exercise host discovery or permissions."""

import json
import re
import tomllib

import frontmatter
import pytest
import yaml

from paths import ROOT, SRC_PLUGINS_DIR

HARNESSES = ("claude", "copilot", "codex")
SKILLS = ("creating-agents", "creating-skills")
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
MANUAL_POLICY = {"policy": {"allow_implicit_invocation": False}}
SOURCE_HEADINGS = {
    "creating-agents": "## Optional: nilpath-marketplace Source Authoring",
    "creating-skills": "## Opt-In Marketplace Source Mode",
}
FENCES = re.compile(
    r"(?m)^(?P<fence>`{3,}|~{3,})(?P<language>[^\n]*)\n"
    r"(?P<code>[\s\S]*?)^(?P=fence)[ \t]*$"
)
LINKS = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")
EXAMPLE_LINKS = {
    "skills/creating-agents/templates/researcher.md": {"url"},
    "skills/creating-agents/workflows/create-research-agent.md": {"url"},
    "skills/creating-skills/SKILL.md": {"FORMS.md", "REFERENCE.md"},
    "skills/creating-skills/references/best-practices.md": {
        "DOCX-JS.md", "EXAMPLES.md", "FORMS.md", "OOXML.md", "REDLINING.md",
        "REFERENCE.md", "advanced.md", "details.md", "examples.md", "reference.md",
    },
    "skills/creating-skills/references/common-patterns.md": {
        "api-reference.md", "audiences.md", "budgets.md", "conversions.md",
    },
    "skills/creating-skills/references/official-spec.md": {"examples.md", "reference.md"},
    "skills/creating-skills/references/skill-structure.md": {"forms.md", "reference.md"},
    "skills/creating-skills/templates/router-skill.md": {
        "references/reference-1.md", "references/reference-2.md",
    },
    "skills/creating-skills/workflows/add-reference.md": {
        "references/existing.md", "references/new-reference.md",
    },
}
AGENT_TEMPLATES = {
    "code-reviewer": {"code-reviewer"},
    "debugger": {"debugger"},
    "researcher": {"researcher"},
    "domain-expert": {"domain-expert", "database-expert", "api-expert", "testing-expert"},
}
AGENT_TOOLS = {
    "claude": {
        "code-reviewer": {"Read", "Grep", "Glob"},
        "debugger": {"Read", "Write", "Edit", "Bash", "Glob", "Grep"},
        "researcher": {"Read", "Grep", "Glob", "WebFetch", "WebSearch"},
        "domain-expert": {"Read", "Grep", "Glob"},
    },
    "copilot": {
        "code-reviewer": {"read", "search"},
        "debugger": {"read", "search", "edit", "execute"},
        "researcher": {"read", "search", "web"},
        "domain-expert": {"read", "search"},
    },
}
SKILL_EXAMPLE_FILES = (
    "SKILL.md",
    "templates/simple-skill.md",
    "templates/router-skill.md",
    "references/official-spec.md",
    "references/invocation-and-arguments.md",
    "references/common-patterns.md",
    "references/best-practices.md",
    "references/core-principles.md",
    "references/recommended-structure.md",
    "references/skill-structure.md",
    "workflows/create-domain-expertise-skill.md",
    "workflows/upgrade-to-router.md",
)
INVOCATION_EXAMPLE_FILES = {
    "references/official-spec.md", "references/invocation-and-arguments.md",
    "references/common-patterns.md",
}
SKILL_KEYS = {
    "claude": {
        "name", "description", "disable-model-invocation", "user-invocable",
        "allowed-tools", "argument-hint", "arguments", "context", "agent",
    },
    "copilot": {"name", "description", "disable-model-invocation", "user-invocable"},
    "codex": {"name", "description"},
}
# These teach metadata customization, not complete output skills.
METADATA_ONLY_SKILL_EXAMPLES = {
    ("claude", "references/common-patterns.md", "api-conventions"),
    ("claude", "references/official-spec.md", "commit"),
} | {(harness, "references/skill-structure.md", "skill-name-here") for harness in HARNESSES}


def _plugin(harness):
    return ROOT / "dist" / harness / "plugins/authoring-tools"


def _skill_examples(path):
    text = path.read_text()
    if text.startswith("---\n") and path.name != "SKILL.md":
        return [frontmatter.loads(text)]
    return [
        frontmatter.loads(match["code"].strip())
        for match in FENCES.finditer(text)
        if match["language"] != "jinja" and match["code"].strip().startswith("---\n")
    ]


def _agent_examples(path, harness):
    examples = {}
    for match in FENCES.finditer(path.read_text()):
        code = match["code"].strip()
        if harness == "codex" and match["language"] == "toml":
            data = tomllib.loads(code)
            # Name/description-only customization snippets are intentionally partial.
            if "developer_instructions" not in data:
                continue
            body = data["developer_instructions"].strip()
        elif harness != "codex" and code.startswith("---\n"):
            post = frontmatter.loads(code)
            data, body = post.metadata, post.content
        else:
            continue
        assert data["name"] not in examples, path
        examples[data["name"]] = (data, body)
    return examples


@pytest.mark.parametrize("harness", HARNESSES)
@pytest.mark.parametrize("skill", SKILLS)
def test_authoring_skill_resources_and_entrypoint(harness, skill):
    source = SRC_PLUGINS_DIR / "authoring-tools/skills" / skill
    output = _plugin(harness) / "skills" / skill
    expected = {
        str(path.relative_to(source)).removesuffix(".j2")
        for path in source.rglob("*") if path.is_file()
    }
    assert {"SKILL.md", "references/authoring-targets.md", "references/official-spec.md"} <= expected
    if skill == "creating-agents":
        assert {f"templates/{name}.md" for name in AGENT_TEMPLATES} <= expected
        assert "examples/real-world-agents.md" in expected
        assert {
            f"workflows/{name}.md" for name in (
                "create-read-only-agent", "create-code-writer-agent",
                "create-research-agent", "audit-existing-agent",
            )
        } <= expected
    else:
        assert set(SKILL_EXAMPLE_FILES) | {"workflows/create-new-skill.md"} <= expected
    if harness != "codex":
        expected.remove("agents/openai.yaml")
        assert not (output / "agents").exists()
    else:
        assert yaml.safe_load((output / "agents/openai.yaml").read_text()) == MANUAL_POLICY
        assert {p.name for p in (output / "agents").iterdir()} == {"openai.yaml"}
    assert {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()} == expected
    assert all(path.read_text().strip() for path in output.rglob("*") if path.is_file())
    post = frontmatter.load(str(output / "SKILL.md"))
    assert post.metadata["name"] == skill
    assert post.metadata["description"].strip()
    assert "targets" not in post.metadata
    assert len((output / "SKILL.md").read_text().splitlines()) <= 500
    command = f"${skill}" if harness == "codex" else f"/authoring-tools:{skill}"
    assert f"Invoke explicitly with `{command}`" in post.content
    assert "[authoring-targets.md](references/authoring-targets.md)" in post.content


@pytest.mark.parametrize("harness", HARNESSES)
def test_authoring_registry_version_and_skill_only_manifest(harness):
    registry = json.loads((ROOT / REGISTRIES[harness]).read_text())
    entries = [p for p in registry["plugins"] if p["name"] == "authoring-tools"]
    assert len(entries) == 1
    entry = entries[0]
    relative_path = f"dist/{harness}/plugins/authoring-tools"
    if harness == "codex":
        assert entry["source"] == {"source": "local", "path": f"./{relative_path}"}
        resolved = ROOT / entry["source"]["path"]
    else:
        assert entry["source"] == ("./" if harness == "claude" else "") + relative_path
        resolved = ROOT / entry["source"]
    assert resolved == _plugin(harness)
    source = yaml.safe_load((SRC_PLUGINS_DIR / "authoring-tools/plugin.yaml").read_text())
    manifest = json.loads((resolved / MANIFESTS[harness]).read_text())
    assert manifest["name"] == source["name"] == "authoring-tools"
    assert manifest["version"] == source["version"]
    if harness != "codex":
        assert entry["version"] == source["version"]
    else:
        assert manifest.get("components", {}).get("agents", []) == []
    assert not (resolved / "agents").exists()
    assert not (SRC_PLUGINS_DIR / "authoring-tools/agents").exists()
    assert {p.name for p in (resolved / "skills").iterdir()} == set(SKILLS)


@pytest.mark.parametrize("harness", HARNESSES)
@pytest.mark.parametrize("relative_path", SKILL_EXAMPLE_FILES)
def test_native_skill_examples_parse_with_supported_metadata(harness, relative_path):
    path = _plugin(harness) / "skills/creating-skills" / relative_path
    examples = _skill_examples(path)
    assert examples, path
    for post in examples:
        data = post.metadata
        assert {"name", "description"} <= data.keys() <= SKILL_KEYS[harness], path
        name = data["name"]
        if relative_path == "workflows/create-domain-expertise-skill.md":
            assert name == "build-{domain-name}"
            name = name.replace("{domain-name}", "example-domain")
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name), path
        assert len(name) <= 64
        assert isinstance(data["description"], str) and 0 < len(data["description"]) <= 1024
        if (harness, relative_path, data["name"]) not in METADATA_ONLY_SKILL_EXAMPLES:
            assert post.content.strip(), (path, data["name"])
        for field in ("disable-model-invocation", "user-invocable"):
            if field in data:
                assert isinstance(data[field], bool), path
        assert not re.search(r"\{\{|\{%", post.content), path
    if relative_path == "SKILL.md":
        assert {p.metadata["name"] for p in examples} == {"my-skill-name", "your-skill-name"}
        assert all(set(p.metadata) == {"name", "description"} for p in examples)
    elif relative_path.startswith("templates/"):
        assert len(examples) == 1
        assert set(examples[0].metadata) == {"name", "description"}
        headings = set(re.findall(r"^## (.+)$", examples[0].content, re.MULTILINE))
        assert (
            {"Quick Start", "Instructions", "Examples", "Guidelines"}
            if relative_path == "templates/simple-skill.md"
            else {"Essential Principles", "Routing", "Reference Index", "Workflows Index"}
        ) <= headings
    elif harness in {"copilot", "codex"} and relative_path in INVOCATION_EXAMPLE_FILES:
        deploying = [p for p in examples if p.metadata["name"] == "deploying-preview"]
        assert len(deploying) == 1, path
        if harness == "copilot":
            assert deploying[0].metadata["disable-model-invocation"] is True
        else:
            assert set(deploying[0].metadata) == {"name", "description"}


@pytest.mark.parametrize(
    "relative_path",
    [
        "references/official-spec.md", "references/invocation-and-arguments.md",
        "references/common-patterns.md", "workflows/create-new-skill.md",
    ],
)
def test_codex_explicit_skill_examples_use_separate_policy(relative_path):
    path = _plugin("codex") / "skills/creating-skills" / relative_path
    policies = [
        yaml.safe_load(match["code"]) for match in FENCES.finditer(path.read_text())
        if match["language"] == "yaml"
    ]
    assert policies == [MANUAL_POLICY]
    assert "`agents/openai.yaml`" in path.read_text()


@pytest.mark.parametrize("harness", HARNESSES)
@pytest.mark.parametrize("template", sorted(AGENT_TEMPLATES))
def test_native_agent_templates_preserve_complete_roles_and_permissions(harness, template):
    relative_path = f"skills/creating-agents/templates/{template}.md"
    path = _plugin(harness) / relative_path
    examples = _agent_examples(path, harness)
    assert set(examples) == AGENT_TEMPLATES[template]
    claude_examples = _agent_examples(_plugin("claude") / relative_path, "claude")
    location = {
        "claude": (".claude/agents", ".md"),
        "copilot": (".github/agents", ".agent.md"),
        "codex": (".codex/agents", ".toml"),
    }[harness]
    filename = "<name>" if template == "domain-expert" else template
    assert f"`{location[0]}/{filename}{location[1]}`" in path.read_text()
    for name, (data, body) in examples.items():
        assert data["name"] == name
        assert isinstance(data["description"], str) and data["description"].strip()
        assert body == claude_examples[name][1], (path, name)
        headings = set(re.findall(r"^## (.+)$", body, re.MULTILINE))
        assert {"When Invoked", "Output Format", "Constraints"} <= headings
        assert body.startswith("You are ")
        if template != "debugger":
            assert "Do NOT modify" in body
        else:
            assert "## If Unable to Fix" in body
        if harness == "codex":
            expected_keys = {"name", "description", "developer_instructions"}
            if template != "debugger":
                expected_keys.add("sandbox_mode")
                assert data["sandbox_mode"] == "read-only"
            assert set(data) == expected_keys
        else:
            expected_keys = {"name", "description", "tools"}
            tools = data["tools"]
            if harness == "claude":
                expected_keys.add("model")
                assert data["model"] == "sonnet"
                tools = [tool.strip() for tool in tools.split(",")]
            else:
                assert isinstance(tools, list)
            assert set(data) == expected_keys
            assert set(tools) == AGENT_TOOLS[harness][template]
            assert len(tools) == len(set(tools))


@pytest.mark.parametrize("harness", HARNESSES)
@pytest.mark.parametrize("skill", SKILLS)
def test_native_guidance_uses_active_harness_paths_tools_and_metadata(harness, skill):
    skill_dir = _plugin(harness) / "skills" / skill
    allowed_roots = {
        "claude": {(".claude", "agents"), (".claude", "skills"), (".claude", "commands")},
        "copilot": {
            (".github", "agents"), (".github", "skills"),
            (".agents", "skills"), (".copilot", "skills"),
        },
        "codex": {(".codex", "agents"), (".agents", "skills")},
    }[harness]
    seen_roots = set()
    for path in sorted(skill_dir.rglob("*.md")):
        text = path.read_text()
        if path == skill_dir / "references/authoring-targets.md":
            assert SOURCE_HEADINGS[skill] in text
            text = text.split(SOURCE_HEADINGS[skill], 1)[0]
        roots = set(re.findall(
            r"(\.(?:claude|github|copilot|agents|codex))/(agents|skills|commands)/", text
        ))
        assert roots <= allowed_roots, (path, roots - allowed_roots)
        seen_roots |= roots
        # Literal Jinja is legitimate in the labeled source tutorial, not active instructions.
        assert not re.search(r"\{\{\s*(?:harness|skill_root|ask_user|todo|spawn|skill_ref)\b", text), path
        assert not re.search(r"\{%\s*(?:if|elif|else|endif|raw|endraw)\b", text), path
        if harness == "claude":
            continue
        assert not re.search(
            r"\b(?:Bash|Agent|Skill)\(|\b(?:AskUserQuestion|TodoWrite|WebFetch|WebSearch)\b",
            text,
        ), path
        for match in FENCES.finditer(text):
            code = match["code"]
            assert not re.search(r"\$ARGUMENTS|\$\{CLAUDE_|!`", code), path
            unsupported = (
                "targets|permissionMode|disallowedTools|allowed-tools|context|"
                "arguments|argument-hint|agent|hooks|effort"
            )
            if harness == "codex":
                unsupported += "|tools|disable-model-invocation|user-invocable"
            assert not re.search(rf"(?m)^(?:{unsupported})\s*[:=]", code), path
            assert not re.search(
                r"""(?m)^model\s*[:=]\s*["']?(?:small|medium|large|xlarge|haiku|sonnet|opus)\b""",
                code,
            ), path
    expected_root = {
        ("claude", "creating-agents"): (".claude", "agents"),
        ("claude", "creating-skills"): (".claude", "skills"),
        ("copilot", "creating-agents"): (".github", "agents"),
        ("copilot", "creating-skills"): (".github", "skills"),
        ("codex", "creating-agents"): (".codex", "agents"),
        ("codex", "creating-skills"): (".agents", "skills"),
    }[harness, skill]
    assert expected_root in seen_roots


@pytest.mark.parametrize("harness", HARNESSES)
def test_bundled_markdown_links_resolve(harness):
    broken = []
    checked = set()
    for path in sorted(_plugin(harness).rglob("*.md")):
        text = path.read_text()
        relative_path = str(path.relative_to(_plugin(harness)))
        example_spans = [match.span() for match in FENCES.finditer(text)]
        for match in LINKS.finditer(text):
            target = match[1]
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            # Only documented output placeholders may point outside the real bundle.
            if target in EXAMPLE_LINKS.get(relative_path, set()):
                assert (
                    relative_path == "skills/creating-skills/templates/router-skill.md"
                    or any(start <= match.start() < end for start, end in example_spans)
                ), (path, target)
                continue
            destination = (path.parent / target.split("#", 1)[0]).resolve()
            checked.add(destination)
            if not destination.is_file() or not destination.is_relative_to(_plugin(harness)):
                broken.append(f"{path.relative_to(_plugin(harness))}: {target}")
    assert not broken, "\n".join(broken)
    for skill in SKILLS:
        assert _plugin(harness) / "skills" / skill / "references/authoring-targets.md" in checked


def test_claude_native_skill_features_remain_available():
    path = _plugin("claude") / "skills/creating-skills/references/invocation-and-arguments.md"
    examples = _skill_examples(path)
    by_name = {post.metadata["name"]: post for post in examples}
    assert by_name["deploy"].metadata["allowed-tools"] == "Bash(./scripts/deploy.sh *)"
    assert by_name["deploy"].metadata["disable-model-invocation"] is True
    assert by_name["api-conventions"].metadata["user-invocable"] is False
    assert by_name["fix-issue"].metadata["argument-hint"] == "[issue-number]"
    assert by_name["migrate-component"].metadata["arguments"] == ["component", "from", "to"]
    assert by_name["pr-summary"].metadata["context"] == "fork"
    assert by_name["pr-summary"].metadata["agent"] == "Explore"
    assert "!`gh pr diff`" in by_name["pr-summary"].content
    assert "${CLAUDE_SKILL_DIR}/scripts/validate.py" in by_name["validate-schema"].content

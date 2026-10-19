"""Generated nstack output: inventory, registration, links, and role wiring."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import frontmatter
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HARNESSES = ("claude", "copilot", "codex")
VERSION = yaml.safe_load((ROOT / "src" / "plugins" / "nstack" / "plugin.yaml").read_text())["version"]
SKILLS = {
    "architect",
    "benchmark-checklist",
    "candidate-graft",
    "control-cli",
    "control-ui",
    "create-verification-skill",
    "deslop",
    "figure-it-out",
    "how",
    "maintain-verification-skill",
    "no-comments",
    "nstack-flow",
    "principle-attack-the-premise",
    "principle-boundary-discipline",
    "principle-build-the-lever",
    "principle-encode-lessons-in-structure",
    "principle-exhaust-the-design-space",
    "principle-experience-first",
    "principle-explain-the-number",
    "principle-fix-root-causes",
    "principle-foundational-thinking",
    "principle-guard-the-context-window",
    "principle-laziness-protocol",
    "principle-make-operations-idempotent",
    "principle-migrate-callers-then-delete-legacy-apis",
    "principle-minimize-reader-load",
    "principle-model-the-domain",
    "principle-never-block-on-the-human",
    "principle-outcome-oriented-execution",
    "principle-prove-it-works",
    "principle-redesign-from-first-principles",
    "principle-separate-before-serializing-shared-state",
    "principle-sequence-verifiable-units",
    "principle-subtract-before-you-add",
    "principle-test-behavior-not-implementation",
    "principle-type-system-discipline",
    "review-panel",
    "setup-nstack",
    "show-me-your-work",
    "swarm",
    "tdd",
    "technical-writing",
    "typescript-best-practices",
    "unslop",
    "why",
}
AGENT_FILES = {
    "claude": ("agents/implementation/nstack-agent.md", "agents/implementation/nstack-reader.md", "agents/review/comment-sicko.md"),
    "copilot": (
        "com.github.copilot/agents/nstack-agent.agent.md",
        "com.github.copilot/agents/nstack-reader.agent.md",
        "com.github.copilot/agents/comment-sicko.agent.md",
    ),
    "codex": ("agents/nstack-agent.toml", "agents/nstack-reader.toml", "agents/comment-sicko.toml"),
}
HOOK_FILES = {
    "claude": "hooks/hooks.json",
    "copilot": "com.github.copilot/hooks/hooks.json",
    "codex": "hooks/hooks.json",
}
HOOK_DIRS = {"claude": "hooks", "copilot": "com.github.copilot/hooks", "codex": "hooks"}


def hook_command(harness: str, command: str) -> str:
    return f'python3 "$CLAUDE_PLUGIN_ROOT/{HOOK_DIRS[harness]}/nstack_config.py" {command} || true'
MANIFESTS = {
    "claude": ".claude-plugin/plugin.json",
    "copilot": "plugin.json",
    "codex": ".codex-plugin/plugin.json",
}
SKILL_ROLES = {
    "how": {"how-explorer", "how-explainer"},
    "why": {"why-investigator", "why-synthesizer"},
    "swarm": {"swarm-worker"},
    "candidate-graft": {"candidate-graft-runner", "candidate-graft-judge"},
    "architect": {"architect-runner"},
    "review-panel": {"review-panel-reviewer"},
    "nstack-flow": {"implementer", "implementer-hard", "judgment"},
    "maintain-verification-skill": {"how-explorer"},
}
LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
PLAYBOOKS = {"feature.md", "bug-fix.md", "investigation.md"}


def plugin_dir(harness: str) -> Path:
    return ROOT / "dist" / harness / "plugins" / "nstack"


@pytest.mark.parametrize("harness", HARNESSES)
def test_inventory(harness):
    root = plugin_dir(harness)
    skills = {p.parent.name for p in (root / "skills").glob("*/SKILL.md")}
    assert skills == SKILLS
    for agent in AGENT_FILES[harness]:
        assert (root / agent).is_file()
    assert {p.name for p in (root / "skills" / "nstack-flow" / "playbooks").iterdir()} == PLAYBOOKS
    assert (root / "README.md").is_file()


@pytest.mark.parametrize("harness", HARNESSES)
def test_manifest_version(harness):
    manifest = json.loads((plugin_dir(harness) / MANIFESTS[harness]).read_text())
    assert manifest["version"] == VERSION == "0.0.1"


def test_codex_manifest_lists_the_agents():
    manifest = json.loads((plugin_dir("codex") / MANIFESTS["codex"]).read_text())
    assert manifest["components"]["agents"] == ["agents/comment-sicko.toml", "agents/nstack-agent.toml", "agents/nstack-reader.toml"]
    writer, reader = (tomllib.loads((plugin_dir("codex") / f).read_text()) for f in AGENT_FILES["codex"][:2])
    assert (writer["name"], reader["name"]) == ("nstack-agent", "nstack-reader")
    assert "model" not in writer and "model" not in reader
    assert "model_reasoning_effort" not in writer and "model_reasoning_effort" not in reader
    assert reader["sandbox_mode"] == "read-only" and "sandbox_mode" not in writer


@pytest.mark.parametrize("harness", HARNESSES)
def test_hooks_run_the_script_at_launch_and_session_start(harness):
    hooks = json.loads((plugin_dir(harness) / HOOK_FILES[harness]).read_text())["hooks"]
    if harness == "copilot":
        (launch,) = hooks["preToolUse"]
        (start,) = hooks["sessionStart"]
        assert (launch["matcher"], launch["bash"]) == ("task", hook_command(harness, "hook"))
        assert start["bash"] == hook_command(harness, "session-start")
    else:
        (group,) = hooks["PreToolUse"]
        assert group["matcher"] == ("Agent" if harness == "claude" else "spawn_agent")
        assert group["hooks"][0]["command"] == hook_command(harness, "hook")
        assert hooks["SessionStart"][0]["hooks"][0]["command"] == hook_command(harness, "session-start")


LAUNCH_SYNTAX = {
    "claude": 'Agent(subagent_type="nstack:implementation:nstack-agent")',
    "copilot": "agent type `nstack:nstack-agent`",
    "codex": "`spawn_agent` with `agent_type` `nstack-agent`",
}


@pytest.mark.parametrize("harness", HARNESSES)
def test_delegating_skills_inline_the_launch(harness):
    root = plugin_dir(harness)
    assert not (root / "skills" / "nstack-flow" / "references" / "delegation.md").exists()
    for skill in (set(SKILL_ROLES) - {"architect"}) | {"setup-nstack"}:
        text = (root / "skills" / skill / "SKILL.md").read_text()
        assert LAUNCH_SYNTAX[harness] in text, skill
    for skill in ("candidate-graft", "review-panel"):
        assert "`nstack panels`" in (root / "skills" / skill / "SKILL.md").read_text(), skill


@pytest.mark.parametrize("harness", HARNESSES)
def test_specialist_skills_carry_only_the_launch_sentence(harness):
    shared_rules = (
        "never set a model or effort yourself",
        "Briefs must stand alone",
        "don't do the delegated work yourself",
        "If the line is missing",
        "return the result to that caller",
    )
    for skill in ("how", "why", "swarm", "candidate-graft", "review-panel", "architect"):
        text = (plugin_dir(harness) / "skills" / skill / "SKILL.md").read_text()
        for rule in shared_rules:
            assert rule not in text, f"{skill} repeats {rule!r}"


@pytest.mark.parametrize("harness", HARNESSES)
def test_only_setup_knows_about_the_hook_internals(harness):
    root = plugin_dir(harness)
    leaks = []
    for md in sorted((root / "skills").rglob("*.md")):
        if md.relative_to(root / "skills").parts[0] == "setup-nstack":
            continue
        text = md.read_text()
        for token in ("nstack_config", "hooks.json", "[nstack-hook]", "models.json", "nstack-reader"):
            if token in text:
                leaks.append(f"{md.relative_to(root)}: {token}")
    assert leaks == []


@pytest.mark.parametrize("harness", ("claude", "copilot"))
def test_agents_have_no_fixed_model_and_reader_is_read_only(harness):
    writer, reader = (frontmatter.load(plugin_dir(harness) / f) for f in AGENT_FILES[harness][:2])
    assert (writer["name"], reader["name"]) == ("nstack-agent", "nstack-reader")
    for post in (writer, reader):
        assert "model" not in post.metadata
        assert "[nstack-hook]" in post.content
    tools = reader["tools"]
    if harness == "claude":
        assert tools == "Read, Glob, Grep"
    else:
        assert tools == ["read", "search"]


def test_registries_route_to_nstack():
    claude = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    copilot = json.loads((ROOT / ".github" / "plugin" / "marketplace.json").read_text())
    codex = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text())
    by_name = lambda reg: {p["name"]: p for p in reg["plugins"]}  # noqa: E731
    assert by_name(claude)["nstack"]["source"] == "./dist/claude/plugins/nstack"
    assert by_name(claude)["nstack"]["version"] == VERSION
    assert by_name(copilot)["nstack"]["source"] == "dist/copilot/plugins/nstack"
    assert by_name(copilot)["nstack"]["version"] == VERSION
    assert by_name(codex)["nstack"]["source"]["path"] == "./dist/codex/plugins/nstack"


@pytest.mark.parametrize("harness", HARNESSES)
def test_markdown_links_resolve(harness):
    root = plugin_dir(harness)
    broken = []
    for md in root.rglob("*.md"):
        for target in LINK_RE.findall(md.read_text()):
            if target.startswith(("http://", "https://", "mailto:")) or not target.endswith((".md", "/")):
                continue
            if not (md.parent / target).exists():
                broken.append(f"{md.relative_to(root)} -> {target}")
    assert broken == []


@pytest.mark.parametrize("harness", HARNESSES)
def test_no_template_or_foreign_harness_syntax(harness):
    root = plugin_dir(harness)
    foreign = {
        "claude": ["update_plan", "the todo list"],
        "copilot": ["Agent(subagent_type", "TodoWrite", "AskUserQuestion", "update_plan", "CLAUDE_PLUGIN_ROOT"],
        "codex": ["Agent(subagent_type", "TodoWrite", "AskUserQuestion", "CLAUDE_PLUGIN_ROOT"],
    }[harness]
    for md in root.rglob("*.md"):
        text = md.read_text()
        assert "{{" not in text and "{%" not in text, md
        for token in foreign:
            assert token not in text, f"{md.relative_to(root)} contains {token!r}"


@pytest.mark.parametrize("harness", HARNESSES)
def test_scripts_are_executable(harness):
    root = plugin_dir(harness)
    for path in (root / HOOK_DIRS[harness] / "nstack_config.py", root / "skills" / "nstack-flow" / "scripts" / "publish_draft.py"):
        assert path.is_file() and os.access(path, os.X_OK), path


@pytest.mark.parametrize("harness", HARNESSES)
def test_role_catalog_matches_the_skills(harness, tmp_path):
    root = plugin_dir(harness)
    helper = root / HOOK_DIRS[harness] / "nstack_config.py"
    proc = subprocess.run(
        [sys.executable, str(helper), "roles"],
        capture_output=True, text=True, check=True, env={**os.environ, "HOME": str(tmp_path)},
    )
    catalog = {role["id"] for role in json.loads(proc.stdout)["roles"]}
    assert not (root / HOOK_DIRS[harness] / "roles").exists()
    used = set().union(*SKILL_ROLES.values())
    assert used == catalog
    for skill, roles in SKILL_ROLES.items():
        text = (root / "skills" / skill / "SKILL.md").read_text()
        for role in roles:
            assert f"`{role}`" in text or f"role={role}" in text, f"{skill} does not name role {role}"
        assert "[nstack role=" in text, f"{skill} does not show a launch marker"


@pytest.mark.parametrize("harness", HARNESSES)
def test_component_names_are_unique_across_the_marketplace(harness):
    plugins = ROOT / "dist" / harness / "plugins"
    skills = [p.parent.name for p in plugins.glob("*/skills/*/SKILL.md")]
    assert len(skills) == len(set(skills)), sorted(s for s in skills if skills.count(s) > 1)
    agents = [p.name.split(".")[0] for p in plugins.glob("*/**/agents/**/*") if p.is_file() and p.suffix in {".md", ".toml"}]
    assert len(agents) == len(set(agents)), sorted(a for a in agents if agents.count(a) > 1)


@pytest.mark.parametrize("harness", HARNESSES)
def test_coordinator_has_poteto_style_sections(harness):
    text = (plugin_dir(harness) / "skills" / "nstack-flow" / "SKILL.md").read_text()
    headings = re.findall(r"^## (.+)$", text, re.M)
    for heading in ("Non-negotiables", "Principles", "Autonomy", "Subagents", "Writing the reply", "Comments", "Playbooks"):
        assert heading in headings
    assert "[nstack role=" in text

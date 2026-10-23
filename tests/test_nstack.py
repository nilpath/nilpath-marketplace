"""Generated nstack inventory and instruction wiring, not runtime model obedience."""

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
    "python-best-practices",
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
    assert manifest["version"] == VERSION


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


@pytest.mark.parametrize("harness", HARNESSES)
def test_execution_entries_require_the_same_sign_off_contract(harness):
    """Protect required-read wiring, not runtime consent enforcement."""
    skills = plugin_dir(harness) / "skills"
    contract = skills / "nstack-flow" / "references" / "sign-off.md"
    assert contract.is_file()
    entries = {
        "nstack-flow/SKILL.md": "## Non-negotiables",
        "nstack-flow/playbooks/feature.md": "1. `how`",
        "nstack-flow/playbooks/bug-fix.md": "1. Reproduce",
        "figure-it-out/SKILL.md": "## Phase A",
        "architect/SKILL.md": "## Start",
        "candidate-graft/SKILL.md": "## Phase A",
        "show-me-your-work/SKILL.md": "## The format",
        "principle-build-the-lever/SKILL.md": "- Do the first unit",
        "principle-never-block-on-the-human/SKILL.md": "- Proceed",
        "principle-foundational-thinking/SKILL.md": "**Scaffold first.**",
    }
    for relative, first_step in entries.items():
        path = skills / relative
        text = path.read_text()
        required = re.search(r"Read the \[sign-off contract\]\(([^)]+)\)", text)
        assert required is not None, f"{relative} needs an active required-read link"
        assert (path.parent / required[1]).resolve() == contract.resolve(), relative
        assert required.start() < text.index(first_step), relative
    question = yaml.safe_load((ROOT / "src" / "harnesses" / f"{harness}.yaml").read_text())["prose"]["ask_user"]
    assert question in contract.read_text()


@pytest.mark.parametrize("harness", HARNESSES)
def test_bounded_handoffs_transmit_owner_authority_without_a_second_checkpoint(harness):
    skills = plugin_dir(harness) / "skills"
    contract = (skills / "nstack-flow" / "references" / "sign-off.md").read_text()
    handoff = contract.split("## Delegated execution\n", 1)[1].split("## Default checkpoint", 1)[0]
    coordinator = (skills / "nstack-flow" / "SKILL.md").read_text()
    launch = coordinator.split("Before any implementing launch,", 1)[1].split("\n\n", 1)[0]
    bug_fix = (skills / "nstack-flow" / "playbooks" / "bug-fix.md").read_text()
    bug_brief = re.search(r"^4\. (.+)$", bug_fix, re.M)[1]
    custom = (skills / "figure-it-out" / "SKILL.md").read_text()
    custom_brief = custom.split("## Phase C:", 1)[1].split("## Phase D:", 1)[0]
    for field in ("attributable", "approval or grant", "context or evidence", "scope", "exclusions", "stop conditions"):
        for brief in (handoff, launch, bug_brief, custom_brief):
            assert field in brief, f"{harness} handoff lacks {field}"
    assert handoff.index("The coordinator validates") < handoff.index("The delegate executes")
    assert "without requesting user approval again" in handoff
    assert "human reply channel is not a fresh checkpoint" in handoff
    assert "BLOCKED to the coordinator" in handoff and "cannot self-authorize" in handoff
    checkpoint = contract.split("## Default checkpoint", 1)[1].split("## Explicit grants", 1)[0]
    assert "If the coordinator has no user reply channel" in checkpoint
    assert "An authorized delegate follows the bounded handoff" in checkpoint
    continuation = contract.split("## Execution, changes, and continuation", 1)[1]
    assert "coordinator must recover the actual proposal, attributable user approval or grant" in continuation
    assert "previous worker activity, or a bare claim" in continuation
    delegate_resume = continuation.split("A continuing delegate", 1)[1]
    assert "bounded brief and current workspace" in delegate_resume
    assert "return BLOCKED to the coordinator" in delegate_resume


@pytest.mark.parametrize("harness", HARNESSES)
def test_helper_writes_respect_governed_scope_and_scratch_path_precedence(harness):
    skills = plugin_dir(harness) / "skills"
    actions = {
        "principle-foundational-thinking": "**Scaffold first.**",
        "principle-never-block-on-the-human": "- Proceed",
        "principle-build-the-lever": "- Do the first unit",
    }
    for skill, action in actions.items():
        text = (skills / skill / "SKILL.md").read_text()
        boundary = text.split("Read the [sign-off contract]", 1)[1].split("\n\n", 1)[0]
        assert "inside a workflow governed by it" in boundary, skill
        assert "Outside governed workflows" in boundary and "no sign-off checkpoint" in boundary, skill
        assert text.index(boundary) < text.index(action), skill
    lever = (skills / "principle-build-the-lever" / "SKILL.md").read_text()
    assert lever.index("only to authorized implementation") < lever.index("- Do the first unit")
    diff_requirement = next(line for line in lever.splitlines() if "in the diff" in line)
    assert diff_requirement.startswith("- During governed preparation,")
    assert diff_requirement.index("No product diff is required") < diff_requirement.index("Otherwise, applying this principle")
    commit = next(line for line in lever.splitlines() if line.startswith("- Commit the lever"))
    assert "caller's commit limits" in commit and "covering implementation authority" in commit
    trail = (skills / "show-me-your-work" / "SKILL.md").read_text()
    location = trail.split("## Where it lives", 1)[1].split("## Rules", 1)[0]
    assert location.index("preapproval logs in assigned scratch paths outside product source") < location.index("`decisions.tsv`")
    assert location.index("caller-assigned path takes precedence") < location.index("`decisions.tsv`")
    assert "one log rather than starting a second trail" in location
    promotion = next(line for line in location.splitlines() if "promote a scratch log" in line)
    assert promotion.startswith("In governed workflows,")
    assert "covering authority" in promotion and "covering implementation authority" in promotion
    assert "caller's write, commit, and delivery limits" in promotion
    assert "Standalone use does not acquire a sign-off checkpoint" in trail


@pytest.mark.parametrize("harness", HARNESSES)
def test_custom_workflow_gate_and_encoding_corrections_stay_in_scope(harness):
    text = (plugin_dir(harness) / "skills" / "figure-it-out" / "SKILL.md").read_text()
    loop = text.split("## Phase C:", 1)[1].split("## Phase D:", 1)[0]
    gate = next(line for line in loop.splitlines() if "If the gate itself is wrong" in line)
    assert "only when covering authority includes that correction" in gate
    final = text.split("## Phase E:", 1)[1]
    assert final.index("Within approved scope") < final.index("encode recurring corrections")
    assert "CI gate, a lint rule, a check, or a script" in final
    for instruction in (gate, final):
        assert "Report and propose out-of-scope" in instruction and "separately" in instruction


@pytest.mark.parametrize("harness", HARNESSES)
def test_compact_bug_fix_proposals_keep_required_execution_steps(harness):
    skills = plugin_dir(harness) / "skills"
    contract = (skills / "nstack-flow" / "references" / "sign-off.md").read_text()
    proportion = contract.split("## Proportionate proposals", 1)[1].split("## Execution,", 1)[0]
    bug_fix = (skills / "nstack-flow" / "playbooks" / "bug-fix.md").read_text()
    steps = {int(number): body for number, body in re.findall(r"^(\d+)\. (.+)$", bug_fix, re.M)}
    for instruction in (proportion, steps[3]):
        assert "only unnecessary preapproval architecture fan-out" in instruction
        assert all(step in instruction for step in ("implementer", "verification", "review-panel"))
    assert "required implementer delegation" in proportion and "does not permit inline fallback" in proportion
    assert "mandatory for both fix sizes" in steps[4]
    coordinator = (skills / "nstack-flow" / "SKILL.md").read_text()
    assert "Never do the delegated work inline." in steps[4] and "Never do the delegated work inline." in coordinator
    assert "blocked" in steps[4] and "BLOCKED" in steps[4]
    assert (
        bug_fix.index("3. Plan the fix")
        < bug_fix.index("4. Within that authority, delegate implementation")
        < bug_fix.index("5. Verify on the same surface")
        < bug_fix.index("7. Run the **review-panel** skill")
    )


@pytest.mark.parametrize("harness", HARNESSES)
def test_pending_proposal_replies_do_not_require_completion_results(harness):
    skills = plugin_dir(harness) / "skills"
    coordinator = (skills / "nstack-flow" / "SKILL.md").read_text()
    reply = coordinator.split("## Writing the reply", 1)[1].split("## Comments", 1)[0]
    contract = (skills / "nstack-flow" / "references" / "sign-off.md").read_text()
    checkpoint = contract.split("## Default checkpoint", 1)[1].split("## Explicit grants", 1)[0]
    assert "While awaiting sign-off, present the proposal required by the sign-off contract and end the turn" in reply
    assert "end the turn without launching implementing workers" in checkpoint
    assert "Completion-only reporting does not apply yet" in reply
    assert "On completion, keep every section the playbook's reply names" in reply
    delivery = next(line for line in reply.splitlines() if "Include a PR link" in line)
    assert delivery.startswith("When a playbook completes, report its actual results")
    assert "only when authorized delivery produced one" in delivery
    assert "Never invent a fix, verification result, review outcome, or PR" in delivery


@pytest.mark.parametrize("harness", HARNESSES)
def test_nested_design_handoffs_keep_execution_with_the_coordinator(harness):
    skills = plugin_dir(harness) / "skills"
    for relative in (
        "nstack-flow/playbooks/feature.md",
        "nstack-flow/playbooks/bug-fix.md",
        "figure-it-out/SKILL.md",
    ):
        text = (skills / relative).read_text()
        assert re.search(r"`?architect`?.{0,100}design.only", text, re.I), relative
        assert "sign-off" in text and "approval" in text, relative
    architect = (skills / "architect" / "SKILL.md").read_text()
    agree = architect.split("## Phase C: Agree\n", 1)[1].split("## Phase D:", 1)[0]
    assert all(term in agree.lower() for term in ("nested", "return", "coordinator", "waiver", "design only"))
    runner = skills / "architect" / "references" / "runner-prompt.md"
    runner_text = runner.read_text()
    targets = {(runner.parent / link).resolve() for link in LINK_RE.findall(runner_text)}
    assert (skills / "architect" / "SKILL.md").resolve() in targets
    assert "artifact-only" in runner_text and "scratch" in runner_text
    assert "Do not implement" in runner_text


@pytest.mark.parametrize("harness", HARNESSES)
def test_candidate_authority_covers_both_launch_and_promotion(harness):
    text = (plugin_dir(harness) / "skills" / "candidate-graft" / "SKILL.md").read_text()
    frame = text.split("## Phase A: Frame", 1)[1].split("## Phase B:", 1)[0]
    launch = text.split("## Phase B: Fan out", 1)[1].split("## Phase C:", 1)[0]
    graft = text.split("## Phase E: Graft", 1)[1].split("## Phase F:", 1)[0]
    assert "design-only" in frame and "code-producing" in frame
    assert "approval" in frame and "standalone" in frame.lower()
    assert "authority" in launch and "brief" in launch
    assert "authority" in graft and "promot" in graft
    assert launch.index("Check authority") < launch.index("Spawn all")
    assert graft.index("check that matching authority") < graft.index("Fold each graft")


@pytest.mark.parametrize("harness", HARNESSES)
def test_active_defaults_cannot_bypass_the_shared_contract(harness):
    skills = plugin_dir(harness) / "skills"
    stale_defaults = {
        "architect/SKILL.md": (
            "Agree (opt-in)",
            "Default: proceed directly to implementation",
            "No human checkpoint",
            "ship as its own commit either way",
        ),
        "figure-it-out/SKILL.md": (
            "Reversible work proceeds",
            "Then execute the design.",
        ),
        "nstack-flow/SKILL.md": (
            '**Session overrides:** "Don\'t stop" / "going to bed"',
            "**Just do it.**",
        ),
        "principle-never-block-on-the-human/SKILL.md": (
            "Since code changes are reversible and reviewable",
            "Reversible actions (write code, edit notes, split tasks) should proceed",
        ),
        "architect/references/rationale-template.md": ("Phase D sign-off", "if a checkpoint was opted into"),
    }
    for relative, forbidden in stale_defaults.items():
        text = (skills / relative).read_text()
        for phrase in forbidden:
            assert phrase not in text, f"{relative} still says {phrase!r}"
    readme = (plugin_dir(harness) / "README.md").read_text()
    assert "unless you ask for a checkpoint" not in readme
    assert "sign-off" in readme

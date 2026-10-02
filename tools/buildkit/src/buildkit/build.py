"""Build orchestration: render src/plugins/* into per-harness dist trees."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .config import HarnessConfig, PluginConfig, SourceConfig, load_config
from .fm import dump_agent_toml, dump_frontmatter, process_frontmatter, split_document
from .manifests import (
    write_claude_plugin_manifest,
    write_codex_plugin_manifest,
    write_copilot_plugin_manifest,
    write_marketplace_registries,
)
from .render import make_environment, render_file

ALL_TARGETS = ("claude", "copilot", "codex")

# Repo-relative paths fully managed (regenerated) by the build. The three
# registry files live at fixed discovery locations outside dist/:
# Claude Code, Codex, and VS Code Copilot respectively.
OWNED_PATHS = (
    Path("dist"),
    Path(".claude-plugin") / "marketplace.json",
    Path(".agents") / "plugins" / "marketplace.json",
    Path(".github") / "plugin" / "marketplace.json",
)


@dataclass
class BuildResult:
    warnings: list[str] = field(default_factory=list)
    written: list[Path] = field(default_factory=list)


def discover_skills(plugin: PluginConfig) -> list[Path]:
    return sorted(p.parent for p in (plugin.src_dir / "skills").glob("*/SKILL.md.j2"))


def discover_agents(plugin: PluginConfig) -> list[Path]:
    return sorted((plugin.src_dir / "agents").glob("*/*.md.j2"))


def _component_targets(fm_data: dict, component: str) -> list[str]:
    targets = fm_data.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError(f"{component}: frontmatter must declare a 'targets' list")
    unknown = [t for t in targets if t not in ALL_TARGETS]
    if unknown:
        raise ValueError(f"{component}: unknown targets {unknown}")
    return targets


def _plugin_dist_dir(out_root: Path, harness: HarnessConfig, plugin: PluginConfig) -> Path:
    return out_root / harness.dist_root / "plugins" / plugin.name


def _build_skill(
    env,
    skill_dir: Path,
    harness: HarnessConfig,
    plugin: PluginConfig,
    cfg: SourceConfig,
    out_root: Path,
    result: BuildResult,
) -> bool:
    name = skill_dir.name
    component = f"{plugin.name}/skill/{name}"
    rendered = render_file(env, skill_dir / "SKILL.md.j2", harness, cfg, skill_name=name)
    fm_data, body = split_document(rendered)
    if harness.id not in _component_targets(fm_data, component):
        return False

    fm_out, warnings = process_frontmatter(fm_data, "skill", harness, cfg, component)
    result.warnings.extend(warnings)

    out_dir = _plugin_dist_dir(out_root, harness, plugin) / harness.output["skills_dir"] / name
    out_dir.mkdir(parents=True, exist_ok=True)
    skill_md = out_dir / "SKILL.md"
    skill_md.write_text(dump_frontmatter(fm_out) + body)
    result.written.append(skill_md)

    for src_file in sorted(skill_dir.rglob("*")):
        if not src_file.is_file() or src_file.name == "SKILL.md.j2":
            continue
        rel = src_file.relative_to(skill_dir)
        if src_file.suffix == ".j2":
            out_file = out_dir / rel.with_suffix("")
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(render_file(env, src_file, harness, cfg, skill_name=name))
        else:
            out_file = out_dir / rel
            out_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src_file, out_file)
            shutil.copymode(src_file, out_file)
        result.written.append(out_file)
    return True


def _build_agent(
    env,
    agent_file: Path,
    harness: HarnessConfig,
    plugin: PluginConfig,
    cfg: SourceConfig,
    out_root: Path,
    result: BuildResult,
) -> str | None:
    """Render one agent for one harness. Returns the output filename when the
    agent targets this harness, else None."""
    name = agent_file.stem.removesuffix(".md")
    category = agent_file.parent.name
    component = f"{plugin.name}/agent/{category}/{name}"
    rendered = render_file(env, agent_file, harness, cfg)
    fm_data, body = split_document(rendered)
    if harness.id not in _component_targets(fm_data, component):
        return None
    if not harness.supports_kind("agent"):
        raise ValueError(f"{component}: targets {harness.id}, which has no agent output")

    fm_out, warnings = process_frontmatter(fm_data, "agent", harness, cfg, component)
    result.warnings.extend(warnings)

    suffix = harness.output.get("agent_suffix", ".md")
    out_dir = _plugin_dist_dir(out_root, harness, plugin) / harness.output["agents_dir"]
    if harness.id == "claude":
        out_dir = out_dir / category
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{name}{suffix}"
    if harness.agent_format == "toml":
        content, toml_warnings = dump_agent_toml(fm_out, body)
        result.warnings.extend(f"{component}: {w}" for w in toml_warnings)
        out_file.write_text(content)
    else:
        out_file.write_text(dump_frontmatter(fm_out) + body)
    result.written.append(out_file)
    return out_file.name


def build(
    repo_root: Path, targets: tuple[str, ...] = ALL_TARGETS, out_root: Path | None = None
) -> BuildResult:
    cfg = load_config(repo_root)
    out_root = out_root or repo_root
    env = make_environment()
    result = BuildResult()

    # Full regeneration: clean everything the build owns.
    for rel in OWNED_PATHS:
        path = out_root / rel
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    included: dict[str, list] = {target: [] for target in targets}
    for plugin in cfg.plugins:
        for target in targets:
            harness = cfg.harnesses[target]
            plugin_dir = _plugin_dist_dir(out_root, harness, plugin)
            skill_count = 0
            agent_files: list[str] = []
            for skill_dir in discover_skills(plugin):
                if _build_skill(env, skill_dir, harness, plugin, cfg, out_root, result):
                    skill_count += 1
            for agent_file in discover_agents(plugin):
                written = _build_agent(env, agent_file, harness, plugin, cfg, out_root, result)
                if written:
                    agent_files.append(written)

            if skill_count == 0 and not agent_files:
                continue  # no components for this harness: no tree, no registry entry
            included[target].append(plugin)

            readme = plugin.src_dir / "README.md"
            if readme.exists():
                plugin_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(readme, plugin_dir / "README.md")
                result.written.append(plugin_dir / "README.md")

            if target == "claude":
                result.written += write_claude_plugin_manifest(plugin_dir, plugin)
            elif target == "copilot":
                result.written += write_copilot_plugin_manifest(plugin_dir, plugin)
            elif target == "codex":
                result.written += write_codex_plugin_manifest(plugin_dir, plugin, agent_files)

    result.written += write_marketplace_registries(out_root, cfg, included)
    return result


def check(repo_root: Path, targets: tuple[str, ...] = ALL_TARGETS) -> list[str]:
    """Rebuild into a temp tree and diff against the committed output."""
    import tempfile

    diffs: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        build(repo_root, targets, out_root=tmp_root)
        for rel in OWNED_PATHS:
            expected_root, actual_root = tmp_root / rel, repo_root / rel
            expected = {
                p.relative_to(tmp_root): p for p in expected_root.rglob("*") if p.is_file()
            } if expected_root.is_dir() else ({rel: expected_root} if expected_root.exists() else {})
            actual = {
                p.relative_to(repo_root): p for p in actual_root.rglob("*") if p.is_file()
            } if actual_root.is_dir() else ({rel: actual_root} if actual_root.exists() else {})
            for missing in sorted(set(expected) - set(actual)):
                diffs.append(f"missing: {missing}")
            for extra in sorted(set(actual) - set(expected)):
                diffs.append(f"stale: {extra}")
            for common in sorted(set(expected) & set(actual)):
                if expected[common].read_bytes() != actual[common].read_bytes():
                    diffs.append(f"differs: {common}")
    return diffs

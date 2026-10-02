"""Build orchestration: render src/ into per-harness output trees."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .config import HarnessConfig, SourceConfig, load_config
from .fm import dump_agent_toml, dump_frontmatter, process_frontmatter, split_document
from .manifests import (
    write_claude_manifests,
    write_codex_manifests,
    write_copilot_manifests,
)
from .render import make_environment, render_file

ALL_TARGETS = ("claude", "copilot", "codex")


@dataclass
class BuildResult:
    warnings: list[str] = field(default_factory=list)
    written: list[Path] = field(default_factory=list)


def discover_skills(cfg: SourceConfig) -> list[Path]:
    return sorted(
        p.parent for p in (cfg.root / "skills").glob("*/SKILL.md.j2")
    )


def discover_agents(cfg: SourceConfig) -> list[Path]:
    return sorted((cfg.root / "agents").glob("*/*.md.j2"))


def owned_paths(cfg: SourceConfig, targets: tuple[str, ...] = ALL_TARGETS) -> list[Path]:
    """Repo-relative paths fully managed (regenerated) by the build."""
    plugin_name = cfg.plugin["name"]
    pdir = Path("plugins") / plugin_name
    owned: list[Path] = []
    for target in targets:
        harness = cfg.harnesses[target]
        for key in ("skills_dir", "agents_dir"):
            if key in harness.output:
                owned.append(Path(harness.output[key]))
    if "claude" in targets:
        owned += [
            pdir / ".claude-plugin" / "plugin.json",
            Path(".claude-plugin") / "marketplace.json",
            pdir / ".mcp.json",
        ]
    if "copilot" in targets:
        owned += [pdir / "plugin.json", pdir / "mcp.json"]
    if "codex" in targets:
        owned += [
            pdir / ".codex-plugin" / "plugin.json",
            pdir / ".codex-mcp.json",
            Path(".agents") / "plugins" / "marketplace.json",
            Path(".well-known") / "skills",
        ]
    return owned


def _component_targets(fm_data: dict, component: str) -> list[str]:
    targets = fm_data.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError(f"{component}: frontmatter must declare a 'targets' list")
    unknown = [t for t in targets if t not in ALL_TARGETS]
    if unknown:
        raise ValueError(f"{component}: unknown targets {unknown}")
    return targets


def _build_skill(
    env, skill_dir: Path, harness: HarnessConfig, cfg: SourceConfig, out_root: Path, result: BuildResult
) -> dict | None:
    """Render one skill for one harness. Returns an index entry (name,
    description, files) when the skill targets this harness, else None."""
    name = skill_dir.name
    rendered = render_file(env, skill_dir / "SKILL.md.j2", harness, cfg, skill_name=name)
    fm_data, body = split_document(rendered)
    if harness.id not in _component_targets(fm_data, f"skill/{name}"):
        return None

    fm_out, warnings = process_frontmatter(fm_data, "skill", harness, cfg, f"skill/{name}")
    result.warnings.extend(warnings)

    out_dir = out_root / harness.output["skills_dir"] / name
    out_dir.mkdir(parents=True, exist_ok=True)
    skill_md = out_dir / "SKILL.md"
    skill_md.write_text(dump_frontmatter(fm_out) + body)
    result.written.append(skill_md)

    files = ["SKILL.md"]
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
        files.append(str(out_file.relative_to(out_dir)))
    return {"name": name, "description": fm_data["description"], "files": files}


def _build_agent(
    env, agent_file: Path, harness: HarnessConfig, cfg: SourceConfig, out_root: Path, result: BuildResult
) -> str | None:
    """Render one agent for one harness. Returns the output filename when the
    agent targets this harness, else None."""
    name = agent_file.stem.removesuffix(".md")
    category = agent_file.parent.name
    component = f"agent/{category}/{name}"
    rendered = render_file(env, agent_file, harness, cfg)
    fm_data, body = split_document(rendered)
    if harness.id not in _component_targets(fm_data, component):
        return None
    if not harness.supports_kind("agent"):
        raise ValueError(f"{component}: targets {harness.id}, which has no agent output")

    fm_out, warnings = process_frontmatter(fm_data, "agent", harness, cfg, component)
    result.warnings.extend(warnings)

    suffix = harness.output.get("agent_suffix", ".md")
    out_dir = out_root / harness.output["agents_dir"]
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


def build(repo_root: Path, targets: tuple[str, ...] = ALL_TARGETS, out_root: Path | None = None) -> BuildResult:
    cfg = load_config(repo_root)
    out_root = out_root or repo_root
    env = make_environment()
    result = BuildResult()

    # Clean owned output dirs so removed components disappear.
    for rel in owned_paths(cfg, targets):
        path = out_root / rel
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    skills_index: dict[str, list[dict]] = {}
    agents_index: dict[str, list[str]] = {}
    for target in targets:
        harness = cfg.harnesses[target]
        index: list[dict] = []
        agent_files: list[str] = []
        for skill_dir in discover_skills(cfg):
            entry = _build_skill(env, skill_dir, harness, cfg, out_root, result)
            if entry:
                index.append(entry)
        for agent_file in discover_agents(cfg):
            written = _build_agent(env, agent_file, harness, cfg, out_root, result)
            if written:
                agent_files.append(written)
        skills_index[target] = index
        agents_index[target] = agent_files

    if "claude" in targets:
        result.written += write_claude_manifests(out_root, cfg.plugin)
    if "copilot" in targets:
        result.written += write_copilot_manifests(out_root, cfg.plugin)
    if "codex" in targets:
        result.written += write_codex_manifests(
            out_root, cfg.plugin, skills_index["codex"], agents_index["codex"]
        )
    return result


def check(repo_root: Path, targets: tuple[str, ...] = ALL_TARGETS) -> list[str]:
    """Rebuild into a temp tree and diff against the committed output."""
    import tempfile

    cfg = load_config(repo_root)
    diffs: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        build(repo_root, targets, out_root=tmp_root)
        for rel in owned_paths(cfg, targets):
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

"""One-time importer: seed src/ from the existing Claude-format plugin.

Existing SKILL.md / agent files become .j2 sources nearly verbatim:
- `targets:` is added to frontmatter
- Claude tool names are translated to the canonical vocabulary
- model aliases become canonical tiers
- for portable skills, Claude path variables become {{ skill_root }} and
  Claude-only frontmatter keys are wrapped in {% if harness == "claude" %}
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .toolmap import split_tool_list

TOOL_REVERSE = {
    "Bash": "shell",
    "Read": "file-read",
    "Write": "file-write",
    "Edit": "file-edit",
    "Glob": "glob-search",
    "Grep": "content-search",
    "WebFetch": "web-fetch",
    "WebSearch": "web-search",
    "Agent": "subagent",
    "Skill": "skill",
    "AskUserQuestion": "ask-user",
    "TodoWrite": "todo",
}
MODEL_REVERSE = {"haiku": "small", "sonnet": "medium", "opus": "large", "fable": "xlarge"}

PORTABLE_SKILLS = {
    "engineering-principles",
    "git-commits",
    "git-advanced",
    "using-git-worktrees",
    "git-stacked-prs",
    "gh-pr-review",
    "gh-address-comments",
    "creating-mermaid-diagrams",
}

# Frontmatter keys only Claude understands; wrapped in a harness conditional
# when the component is portable (kept verbatim otherwise).
CLAUDE_ONLY_SKILL_KEYS = {"argument-hint"}

PATH_VAR_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/skills/[a-z0-9-]+|\$\{SKILL_DIR\}")
TEXT_SUFFIXES = {".md", ".sh", ".txt", ".py", ".json", ".yaml", ".yml", ".css", ".mjs"}


def canonicalize_tools(value: str) -> list[str]:
    entries = []
    for raw in split_tool_list(value):
        name, scope = raw, None
        if "(" in raw and raw.endswith(")"):
            name, scope = raw.split("(", 1)
            name, scope = name.strip(), scope[:-1]
        mapped = TOOL_REVERSE.get(name)
        if mapped is None:
            entries.append(f"claude:{raw}")  # raw passthrough (e.g. MCP tool names)
        elif scope:
            entries.append(f"{mapped}({scope})")
        else:
            entries.append(mapped)
    return entries


def _split_frontmatter_lines(text: str) -> tuple[list[str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("file does not start with frontmatter")
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body = "\n".join(lines[i + 1 :])
            if text.endswith("\n"):
                body += "\n"
            return lines[1:i], body
    raise ValueError("frontmatter closing '---' not found")


def _group_keys(fm_lines: list[str]) -> list[tuple[str, list[str]]]:
    """Group frontmatter lines into (key, raw lines) blocks, preserving text."""
    blocks: list[tuple[str, list[str]]] = []
    key_re = re.compile(r"^([A-Za-z][A-Za-z-]*):")
    for line in fm_lines:
        match = key_re.match(line)
        if match:
            blocks.append((match.group(1), [line]))
        elif blocks:
            blocks[-1][1].append(line)
        else:
            raise ValueError(f"unexpected frontmatter line: {line!r}")
    return blocks


def _emit_tools_block(canonical: list[str]) -> list[str]:
    lines = ["tools:"]
    lines += [f'  - "{entry}"' for entry in canonical]
    return lines


def _wrap_claude_only(lines: list[str]) -> list[str]:
    return ['{%- if harness == "claude" %}', *lines, "{%- endif %}"]


def import_skill(skill_dir: Path, out_dir: Path) -> None:
    name = skill_dir.name
    portable = name in PORTABLE_SKILLS
    targets = "[claude, copilot, codex]" if portable else "[claude]"

    fm_lines, body = _split_frontmatter_lines((skill_dir / "SKILL.md").read_text())
    out_lines = ["---"]
    for key, lines in _group_keys(fm_lines):
        if key == "allowed-tools":
            value = lines[0].split(":", 1)[1].strip() + " " + " ".join(
                extra.strip() for extra in lines[1:]
            )
            block = _emit_tools_block(canonicalize_tools(value.strip()))
        elif key in CLAUDE_ONLY_SKILL_KEYS and portable:
            block = _wrap_claude_only(lines)
        else:
            block = lines
        out_lines += block
        if key == "description":
            out_lines.append(f"targets: {targets}")
    out_lines.append("---")

    if portable:
        body = PATH_VAR_RE.sub("{{ skill_root }}", body)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "SKILL.md.j2").write_text("\n".join(out_lines) + "\n" + body)

    for src_file in sorted(skill_dir.rglob("*")):
        if not src_file.is_file() or src_file.name == "SKILL.md":
            continue
        rel = src_file.relative_to(skill_dir)
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if portable and src_file.suffix in TEXT_SUFFIXES:
            text = src_file.read_text()
            if PATH_VAR_RE.search(text):
                dest = dest.with_name(dest.name + ".j2")
                dest.write_text(PATH_VAR_RE.sub("{{ skill_root }}", text))
                continue
        shutil.copyfile(src_file, dest)
        shutil.copymode(src_file, dest)


def import_agent(agent_file: Path, out_file: Path) -> None:
    fm_lines, body = _split_frontmatter_lines(agent_file.read_text())
    out_lines = ["---"]
    for key, lines in _group_keys(fm_lines):
        if key == "tools":
            value: str | list = lines[0].split(":", 1)[1].strip()
            if not value:  # block list form
                value = [l.strip().lstrip("- ").strip() for l in lines[1:] if l.strip()]
            block = _emit_tools_block(canonicalize_tools(value) if isinstance(value, str)
                                      else [c for v in value for c in canonicalize_tools(v)])
        elif key == "model":
            alias = lines[0].split(":", 1)[1].strip()
            tier = MODEL_REVERSE.get(alias)
            if tier is None:
                raise ValueError(f"{agent_file}: unknown model alias {alias!r}")
            block = [f"model: {tier}"]
        else:
            block = lines
        out_lines += block
        if key == "description":
            out_lines.append("targets: [claude]")
    out_lines.append("---")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(out_lines) + "\n" + body)


def import_sources(repo_root: Path, plugin_name: str, force: bool = False) -> list[str]:
    src = repo_root / "src"
    plugin_dir = repo_root / "plugins" / plugin_name
    if (src / "skills").exists() and not force:
        raise SystemExit("src/skills already exists; pass --force to re-import")

    imported: list[str] = []
    for skill_dir in sorted((plugin_dir / "skills").iterdir()):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            import_skill(skill_dir, src / "skills" / skill_dir.name)
            imported.append(f"skill/{skill_dir.name}")
    for agent_file in sorted((plugin_dir / "agents").glob("*/*.md")):
        out = src / "agents" / agent_file.parent.name / (agent_file.stem + ".md.j2")
        import_agent(agent_file, out)
        imported.append(f"agent/{agent_file.parent.name}/{agent_file.stem}")
    return imported

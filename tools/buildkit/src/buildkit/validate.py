"""Source-level validation (structure rules that rendering alone won't catch)."""

from __future__ import annotations

import re
from pathlib import Path

from .config import load_config

MAX_DESCRIPTION_LENGTH = 1024  # Claude skill spec limit

_NAME_RE = re.compile(r"^name:\s*(\S+)\s*$", re.MULTILINE)
_DESC_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)
_TARGETS_RE = re.compile(r"^targets:\s*\[", re.MULTILINE)


def validate_sources(repo_root: Path) -> list[str]:
    cfg = load_config(repo_root)
    errors: list[str] = []

    for skill_file in sorted((cfg.root / "skills").glob("*/SKILL.md.j2")):
        slug = skill_file.parent.name
        text = skill_file.read_text()
        name = _NAME_RE.search(text)
        if not name:
            errors.append(f"skill/{slug}: missing name")
        elif name.group(1) != slug:
            errors.append(f"skill/{slug}: name {name.group(1)!r} != directory name")
        desc = _DESC_RE.search(text)
        if not desc:
            errors.append(f"skill/{slug}: missing description")
        elif len(desc.group(1)) > MAX_DESCRIPTION_LENGTH:
            errors.append(f"skill/{slug}: description exceeds {MAX_DESCRIPTION_LENGTH} chars")
        if not _TARGETS_RE.search(text):
            errors.append(f"skill/{slug}: missing targets")

    for agent_file in sorted((cfg.root / "agents").glob("*/*.md.j2")):
        slug = agent_file.name.removesuffix(".md.j2")
        rel = f"agent/{agent_file.parent.name}/{slug}"
        text = agent_file.read_text()
        name = _NAME_RE.search(text)
        if not name:
            errors.append(f"{rel}: missing name")
        elif name.group(1) != slug:
            errors.append(f"{rel}: name {name.group(1)!r} != file name")
        if not _TARGETS_RE.search(text):
            errors.append(f"{rel}: missing targets")

    return errors

"""nilpath-build: render marketplace sources into per-harness outputs."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .build import ALL_TARGETS, build as run_build, check as run_check
from .importer import import_sources
from .validate import validate_sources

SKILL_TEMPLATE = """\
---
name: {name}
description: TODO one-line description ending with when to use this skill.
targets: [claude]
---

# {title}

TODO
"""


def _find_repo_root() -> Path:
    cur = Path.cwd()
    for candidate in (cur, *cur.parents):
        if (candidate / "src" / "plugin.yaml").exists() or (candidate / ".git").exists():
            return candidate
    raise SystemExit("could not locate repo root (no src/plugin.yaml or .git found)")


@click.group()
@click.option("--repo-root", type=click.Path(exists=True, path_type=Path), default=None)
@click.pass_context
def main(ctx: click.Context, repo_root: Path | None) -> None:
    ctx.obj = repo_root or _find_repo_root()


def _parse_targets(target: str) -> tuple[str, ...]:
    return ALL_TARGETS if target == "all" else (target,)


@main.command()
@click.option("--target", type=click.Choice(["all", *ALL_TARGETS]), default="all")
@click.pass_obj
def build(repo_root: Path, target: str) -> None:
    """Render all components and manifests into the repo."""
    result = run_build(repo_root, _parse_targets(target))
    for warning in result.warnings:
        click.secho(f"warning: {warning}", fg="yellow", err=True)
    click.echo(f"wrote {len(result.written)} files ({target})")


@main.command()
@click.option("--target", type=click.Choice(["all", *ALL_TARGETS]), default="all")
@click.pass_obj
def check(repo_root: Path, target: str) -> None:
    """Fail if committed output drifts from a fresh build (CI gate)."""
    diffs = run_check(repo_root, _parse_targets(target))
    if diffs:
        for diff in diffs:
            click.secho(diff, fg="red", err=True)
        click.secho(f"{len(diffs)} path(s) out of date — run `nilpath-build build`", fg="red")
        sys.exit(1)
    click.echo("output up to date")


@main.command()
@click.pass_obj
def validate(repo_root: Path) -> None:
    """Validate authored sources against structure rules."""
    errors = validate_sources(repo_root)
    if errors:
        for error in errors:
            click.secho(error, fg="red", err=True)
        sys.exit(1)
    click.echo("sources valid")


@main.command("import-sources")
@click.option("--force", is_flag=True, help="Overwrite an existing src/ import")
@click.pass_obj
def import_sources_cmd(repo_root: Path, force: bool) -> None:
    """One-time migration: seed src/ from the existing Claude plugin files."""
    import yaml

    plugin_name = yaml.safe_load((repo_root / "src" / "plugin.yaml").read_text())["name"]
    imported = import_sources(repo_root, plugin_name, force=force)
    click.echo(f"imported {len(imported)} components")


@main.command("new-skill")
@click.argument("name")
@click.pass_obj
def new_skill(repo_root: Path, name: str) -> None:
    """Scaffold src/skills/NAME/SKILL.md.j2."""
    skill_dir = repo_root / "src" / "skills" / name
    if skill_dir.exists():
        raise SystemExit(f"{skill_dir} already exists")
    skill_dir.mkdir(parents=True)
    title = name.replace("-", " ").title()
    (skill_dir / "SKILL.md.j2").write_text(SKILL_TEMPLATE.format(name=name, title=title))
    click.echo(f"created {skill_dir / 'SKILL.md.j2'}")

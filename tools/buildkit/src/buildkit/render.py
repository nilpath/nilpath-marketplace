"""Jinja rendering of authored sources."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, StrictUndefined

from .config import HarnessConfig, SourceConfig


def make_environment() -> Environment:
    # Standard delimiters are safe: templating is opt-in via the .j2 suffix and
    # the authored corpus contains no literal {{ or {% in templated files
    # (supporting files with literal braces use {% raw %} guards).
    return Environment(
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )


def _ref_parts(ref: str) -> dict:
    """Split a qualified component ref into format fields.

    'engineering-workflow:review:code-reviewer' -> plugin/category/name
    'git-tools:git-commits'                     -> plugin/name
    'code-reviewer'                             -> name only
    """
    parts = ref.split(":")
    return {"full": ref, "name": parts[-1], "plugin": parts[0] if len(parts) > 1 else ""}


def _prose_helpers(harness: HarnessConfig) -> dict:
    """Build the harness-specific prose helpers exposed to templates."""
    prose = harness.prose

    def spawn(ref: str) -> str:
        return prose["spawn"].format(**_ref_parts(ref))

    def skill_ref(ref: str) -> str:
        return prose["skill"].format(**_ref_parts(ref))

    helpers: dict = {"spawn": spawn, "skill_ref": skill_ref}
    for key, value in prose.items():
        if key not in ("spawn", "skill"):
            helpers[key] = value  # plain snippets, e.g. todo, ask_user
    return helpers


def render_text(
    env: Environment,
    text: str,
    harness: HarnessConfig,
    cfg: SourceConfig,
    *,
    skill_name: str | None = None,
) -> str:
    context = {
        "harness": harness.id,
        "marketplace": cfg.marketplace,
        **_prose_helpers(harness),
    }
    if skill_name is not None:
        context["skill_name"] = skill_name
        context["skill_root"] = harness.skill_root_template.format(skill_name=skill_name)
    return env.from_string(text).render(**context)


def render_file(
    env: Environment,
    path: Path,
    harness: HarnessConfig,
    cfg: SourceConfig,
    *,
    skill_name: str | None = None,
) -> str:
    return render_text(
        env, path.read_text(), harness, cfg, skill_name=skill_name
    )

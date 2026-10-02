"""Jinja rendering of authored sources."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, StrictUndefined

from .config import HarnessConfig, SourceConfig


def make_environment() -> Environment:
    # Standard delimiters are safe: templating is opt-in via the .j2 suffix and
    # the authored corpus contains no literal {{ or {% in templated files.
    return Environment(
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )


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

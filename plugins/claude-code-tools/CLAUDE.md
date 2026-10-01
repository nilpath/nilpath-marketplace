# Claude Code Tools Context

## GENERATED OUTPUT — do not edit here

Every skill, agent, and manifest in this directory is generated from the repo's
`src/` tree by `nilpath-build` (see `tools/buildkit`). To change a component:

1. Edit the matching `src/skills/<name>/SKILL.md.j2` or `src/agents/<cat>/<name>.md.j2`
2. Run `make build` from the repo root
3. Commit the source and the regenerated output together

`make check` fails CI if this directory drifts from `src/`.

## Versioning Requirements

The version lives in `src/plugin.yaml` only; `make build` propagates it into
every manifest (Claude, Copilot, and Codex). Every release MUST also update:

1. CHANGELOG.md — document changes using Keep a Changelog format
2. README.md — verify/update component counts and tables (plus the root README's portability matrix)

### Version Bumping Rules

- MAJOR (1.0.0 → 2.0.0): Breaking changes, major reorganization
- MINOR (1.0.0 → 1.1.0): New agents, commands, or skills
- PATCH (1.0.0 → 1.0.1): Bug fixes, documentation updates

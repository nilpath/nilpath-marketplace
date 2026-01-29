# Claude Code Tools Context

## Versioning Requirements

IMPORTANT: Every change to this plugin MUST include updates to all four files:

1. .claude-plugin/plugin.json - Bump version using semver
2. ../../.claude-plugin/marketplace.json - Update plugin version in marketplace registry
3. CHANGELOG.md - Document changes using Keep a Changelog format
4. README.md - Verify/update component counts and tables

### Version Bumping Rules

- MAJOR (1.0.0 → 2.0.0): Breaking changes, major reorganization
- MINOR (1.0.0 → 1.1.0): New agents, commands, or skills
- PATCH (1.0.0 → 1.0.1): Bug fixes, doc updates, minor improvements

### Pre-Commit Checklist

Before committing ANY changes:

- [ ] Version bumped in .claude-plugin/plugin.json
- [ ] Version updated in ../../.claude-plugin/marketplace.json
- [ ] CHANGELOG.md updated with changes
- [ ] README.md component counts verified
- [ ] README.md tables accurate (agents, commands, skills)

**Note:** The marketplace.json file is at the root level (.claude-plugin/marketplace.json) and must be kept in sync with the plugin's version.

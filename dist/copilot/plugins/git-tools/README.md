# git-tools

Git and GitHub workflow skills for Claude Code, GitHub Copilot CLI, and Codex.

The bundled script commands use quoted installed paths and keep the repository
working directory. Claude preapproves the declared helpers. Copilot CLI and
Codex retain ordinary manual approval. On those clients, resolve the absolute
skill directory shown in each script-using skill before running its commands.
Native Copilot use inside VS Code is not supported.

## Skills

| Skill | Purpose |
| --- | --- |
| git-commits | Commit message conventions and best practices |
| git-advanced | Rebase, cherry-pick, reflog, bisect |
| git-stacked-prs | Stacked (dependent) pull request workflow |
| using-git-worktrees | Create, list, and remove worktrees |
| gh-pr-review | Create and submit PR reviews with line comments via `gh` |
| gh-address-comments | Fetch and address PR review comments via `gh` |

> Generated from this repo's `src/plugins/git-tools/` sources — edit there, not in `dist/`.

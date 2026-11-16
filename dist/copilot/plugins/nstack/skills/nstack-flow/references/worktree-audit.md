# Worktree audit

[Script](../scripts/worktree-audit.sh). Inventory worktrees and suggest cleanup
buckets for [Worktree cleanup](../playbooks/worktree-cleanup.md). This is an
audit, not a deletion tool.

## Run

Resolve the installed nstack-flow script path. Keep the caller's working
directory; the script selects the requested repository internally.

```bash
bash "<nstack-flow skill directory>/scripts/worktree-audit.sh" -b origin/<base-branch> <repo-path>
```

Both `-b <ref>` and `<repo-path>` are optional; use `--help` for syntax.
The repository defaults to the current Git checkout. Without `-b`, the base
is `origin/HEAD`, then `origin/main`, then `origin/master`. That may not be the
PR target. Select the actual base explicitly when they differ.

Requires Bash, `git`, `jq` and Unix utilities; the optional transcript scan also
uses `rg` and macOS-style `stat`/`date` behavior. PR metadata uses the Origin CLI
when it can read the repository, otherwise `gh`. Missing PR data falls back
to an empty list; it is not proof that no open PR exists.

## Output and limits

Stdout begins with the chosen base, then a size-sorted table containing size,
age, merged state, dirty state, remote state, PR, last chat, bucket and path.
Paths come from `git worktree list`; the main worktree is excluded.

Tracked edits produce `hold-wip`; open/draft PRs produce `hold-open-pr`;
recent transcript activity produces `verify-recent-chat`. Other rows may
suggest `safe` or `review`. These are advice, never deletion authority.

The unchanged upstream transcript lookup uses Cursor project paths and
platform-specific metadata commands. It does not establish actual nstack
session liveness, pinned status or future scheduled activity.
Cross-check candidates against the user's active sessions before removal.
The scan can be slow; run it in the background when the caller supports that.

The script never deletes worktrees or user files. It does perform a best-effort
fetch for an `origin/*` base and creates/removes its own temporary PR cache.
Fetch failures warn that merge data may be stale. Missing repository/base refs
exit 1; invalid CLI options exit 2. A table without a fatal error is not proof
that every optional metadata probe succeeded.

Worktree cleanup retains exact-target/data-loss approval, current/main-workspace
protection and host lifecycle requirements. Do not treat a bucket as permission
to prune.

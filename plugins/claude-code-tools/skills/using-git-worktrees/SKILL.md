---
name: using-git-worktrees
description: Manages git worktrees for feature development — creates, lists, switches between, and removes worktrees. Use when setting up an isolated branch for feature work, running parallel development streams, or cleaning up after a feature is merged.
allowed-tools: Bash(git worktree *), Bash(git branch *)
---

# Using Git Worktrees

Manage git worktrees to keep feature branches isolated from the main working tree.

## Quick Start

Create a worktree for a new feature branch:

```bash
git worktree add ../my-project-feature-name -b feature/my-feature
```

## Common Operations

**Create worktree with a new branch:**

```bash
git worktree add <path> -b <new-branch>
```

**Create worktree from an existing branch:**

```bash
git worktree add <path> <existing-branch>
```

**List all worktrees:**

```bash
git worktree list
```

**Remove a worktree:**

```bash
git worktree remove <path>
```

## Naming Convention

Place worktrees as siblings to the main repo directory:

```
~/projects/my-project/           # main worktree (main branch)
~/projects/my-project-feature/   # feature worktree
```

## Cleanup

After a PR is merged or abandoned:

1. `git worktree remove <path>` — deletes the working directory and releases the lock
2. `git branch -d <branch>` — deletes the local branch (optional, skip if remote tracking is sufficient)

## Remember

- Worktrees share the same `.git` directory — commits made in any worktree are immediately visible everywhere
- You cannot check out the same branch in two worktrees simultaneously
- Always remove worktrees you no longer need — stale worktrees leave lock files that can interfere with git operations

---
name: managing-git
description: Comprehensive git workflow management including well-formatted commits, branch workflows, stacked PRs, merge conflict resolution, history analysis, and advanced operations (rebase, cherry-pick, etc.). Use when working with git repositories or when the user mentions git, commits, branches, pull requests, stacked PRs, merge conflicts, rebasing, or git history.
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Read, Edit, Write
---

# Managing Git

Git workflow guidance following best practices for commits, branching, stacked PRs, and advanced operations.

## What Would You Like To Do?

### Stacked PRs
- **[Create stacked PRs from changes](workflows/create-stacked-prs.md)** - Organize unstaged changes into reviewable stack
- **[Update stack after merge](workflows/update-stack-after-merge.md)** - Rebase and update PR targets after merging
- **[Recover from rebase mistakes](workflows/recover-from-rebase.md)** - Fix rebase errors using reflog
- **[Complete guide](references/stacked-prs.md)** - Comprehensive stacked PR workflow

### Common Tasks
- **Create commit** - See Quick Start below
- **Resolve merge conflicts** - See Conflict Resolution section
- **Analyze history** - See History Analysis section
- **Advanced operations** - See [advanced-operations.md](references/advanced-operations.md)

### References
- **[Commit guidelines](references/commit-guidelines.md)** - Detailed commit formatting and best practices
- **[Common commands](references/common-commands.md)** - Quick reference for git commands

### Templates
- **[Commit message template](templates/commit-message.txt)** - Structured commit message format
- **[PR description template](templates/pr-description.md)** - Stacked PR description format

## Quick Start

### Create Well-Formatted Commit

```bash
git add src/auth.ts src/types.ts
git commit -m "Add JWT authentication

Implements token-based authentication with refresh tokens.
Includes middleware for protected routes and token validation."
```

**Format:**
- First line: Imperative mood, capitalized, < 50 chars
- Blank line
- Body: Wrap at 72 chars, explain what and why

### Create Feature Branch

```bash
git checkout -b feat/user-auth
# Work on feature...
git add <files>
git commit -m "Implement feature"
git push -u origin feat/user-auth
```

**Naming conventions:**
- Use type prefix: `feat/`, `fix/`, `refactor/`, `docs/`
- For stacked PRs: `feat/<stack-name>/<component>` (e.g., `feat/auth/base`, `feat/auth/middleware`)
- Keep names descriptive but concise

### Resolve Merge Conflict

```bash
git status                    # Identify conflicts

# Edit conflicted files, remove markers:
# <<<<<<< HEAD
# =======
# >>>>>>> branch-name

git add <resolved-files>
git commit -m "Merge branch-name

Resolved conflicts in:
- auth.ts: Combined token logic from both branches
- types.ts: Kept incoming interface definitions"
```

## Current Git Context

- Current git status: !`git status`
- Current git diff (staged and unstaged changes): !`git diff HEAD`
- Current branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`

## Core Workflows

### Commits

**Principles:**
1. One logical change per commit
2. Test before committing
3. Clear, imperative messages
4. Commit often

**Example:**
```bash
# Bad: Multiple unrelated changes
git commit -m "Fix bug and add feature and update docs"

# Good: Separate commits
git commit -m "Fix authentication timeout bug"
git commit -m "Add password reset feature"
git commit -m "Update API documentation"
```

See [commit-guidelines.md](references/commit-guidelines.md) for detailed guidance.

### Branch Management

**Feature branch workflow:**
```bash
git checkout main
git pull origin main
git checkout -b feat/new-feature

# Work and commit...
git push -u origin feat/new-feature

# Keep updated
git fetch origin
git rebase origin/main
git push --force-with-lease
```

### Conflict Resolution

**Process:**

1. Identify conflicts:
```bash
git status  # Look for "both modified"
```

2. Open files, resolve conflicts:
```
<<<<<<< HEAD
Current changes
=======
Incoming changes
>>>>>>> branch-name
```

3. Stage and commit:
```bash
git add <resolved-files>
git commit  # Use merge commit message
```

**Tips:**
- Keep changes small to minimize conflicts
- Rebase frequently
- Communicate with team on shared files

### History Analysis

**View history:**
```bash
git log --oneline --graph --all    # Visual history
git log -p                         # History with diffs
git log --author="Name"            # Filter by author
git log --grep="keyword"           # Search messages
```

**Find when bug introduced:**
```bash
git bisect start
git bisect bad                    # Current is bad
git bisect good <commit>          # Known good commit
# Test each commit git provides...
git bisect good/bad               # Mark results
git bisect reset                  # Done
```

**File history:**
```bash
git log -p <file>                 # Changes to file
git blame <file>                  # Who changed each line
```

## Advanced Operations

See [advanced-operations.md](references/advanced-operations.md) for:
- **Interactive rebase** - Reorder, squash, edit commits
- **Cherry-pick** - Apply specific commits
- **Reflog** - Recover lost commits
- **Stash** - Save uncommitted changes
- **Reset** - Undo commits (soft, mixed, hard)
- **Clean** - Remove untracked files

## Guidelines

### Safety Rules

- **Never force push to main/master** - Use revert instead
- **Never rewrite public history** - Others may have pulled it
- **Always backup before complex operations** - Create a branch
- **Test before committing** - Ensure tests pass
- **Use --force-with-lease** - Safer than --force

### Best Practices

**Branching:**
- Work on feature branches, not main
- Keep main stable and deployable
- Delete branches after merge
- Keep feature branches short-lived

**Commits:**
- One logical change per commit
- Test each commit independently
- Write clear messages
- Don't commit secrets or generated files
- Use `.gitignore` appropriately

**Stacked PRs:**
- Plan stack before starting
- Keep each PR < 400 lines
- Ensure tests pass per PR
- Document dependencies in PR descriptions
- Rebase frequently

## Quick Reference

See [common-commands.md](references/common-commands.md) for complete command reference.

**Most used:**
```bash
git status                       # Check status
git add <file>                   # Stage changes
git commit -m "message"          # Commit
git push                         # Push to remote
git pull --rebase                # Update branch
git checkout -b <branch>         # Create branch
git rebase <branch>              # Rebase onto branch
git push --force-with-lease      # Safe force push
git stash                        # Save work temporarily
git reflog                       # View history (recovery)
```

## References

- [commit-guidelines.md](references/commit-guidelines.md) - Commit best practices
- [stacked-prs.md](references/stacked-prs.md) - Comprehensive stacked PR guide
- [advanced-operations.md](references/advanced-operations.md) - Rebase, cherry-pick, reflog
- [common-commands.md](references/common-commands.md) - Command reference

## Workflows

- [create-stacked-prs.md](workflows/create-stacked-prs.md) - Create stack from changes
- [update-stack-after-merge.md](workflows/update-stack-after-merge.md) - Update after merge
- [recover-from-rebase.md](workflows/recover-from-rebase.md) - Fix rebase mistakes

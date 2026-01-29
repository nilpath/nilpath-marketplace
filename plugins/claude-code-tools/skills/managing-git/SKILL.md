---
name: managing-git
description: Comprehensive git workflow management including well-formatted commits, branch workflows, stacked PRs, merge conflict resolution, history analysis, and advanced operations (rebase, cherry-pick, etc.). Use when working with git repositories or when the user mentions git, commits, branches, pull requests, stacked PRs, merge conflicts, rebasing, or git history.
---

# Managing Git

Comprehensive git workflow guidance following best practices for commits, branching, stacked PRs, and advanced operations.

## Quick Start

**Create a well-formatted commit:**
```bash
git add <files>
git commit -m "Add user authentication

Implements JWT-based authentication with refresh tokens.
Includes middleware for protected routes."
```

**Create a feature branch:**
```bash
git checkout -b feature/user-auth
```

**Handle merge conflict:**
```bash
git status                    # Identify conflicted files
# Edit files to resolve conflicts
git add <resolved-files>
git commit -m "Merge feature/user-auth into main"
```

## Core Workflows

### Creating Commits

Follow these principles:

1. **Commit related changes** - One logical change per commit
2. **Commit often** - Small, frequent commits are better
3. **Test before committing** - Ensure tests pass
4. **Write clear messages** - Imperative mood, 50 char summary

**Commit message format:**
```
Capitalized summary (50 chars or less)

Detailed explanation wrapped at 72 characters.
- What was the motivation?
- How does it differ from before?

Use imperative mood: "Fix bug" not "Fixed bug"
```

For detailed commit guidelines and examples, see [commit-guidelines.md](references/commit-guidelines.md).

### Branch Management

**Feature branch workflow:**
```bash
# On main/master/dev
git checkout -b feature/feature-name

# Work on feature
git add <files>
git commit -m "Implement feature"

# Keep branch updated
git fetch origin
git rebase origin/main

# Push feature
git push -u origin feature/feature-name
```

**Branch naming conventions:**
- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates
- `test/` - Test additions/updates

### Stacked PRs Workflow

Stacked PRs allow you to break large features into small, reviewable chunks while maintaining dependencies between them.

**Basic stacked PR pattern:**
```bash
# Base branch (main)
git checkout main

# First PR in stack
git checkout -b feature/auth-base
# Implement base functionality
git commit -m "Add authentication base"
git push -u origin feature/auth-base

# Second PR stacked on first
git checkout -b feature/auth-middleware
# Implement middleware (depends on auth-base)
git commit -m "Add authentication middleware"
git push -u origin feature/auth-middleware

# Third PR stacked on second
git checkout -b feature/auth-ui
# Implement UI (depends on middleware)
git commit -m "Add authentication UI"
git push -u origin feature/auth-ui
```

**Managing stack updates:**
```bash
# When feature/auth-base gets updated
git checkout feature/auth-middleware
git rebase feature/auth-base

git checkout feature/auth-ui
git rebase feature/auth-middleware
```

For detailed stacked PR workflows including handling rebases, merges, and conflicts, see [stacked-prs.md](references/stacked-prs.md).

### Merge Conflict Resolution

**Step-by-step conflict resolution:**

1. **Identify conflicts:**
```bash
git status
# Look for "both modified" files
```

2. **Open conflicted files** - Look for conflict markers:
```
<<<<<<< HEAD
Your current changes
=======
Incoming changes
>>>>>>> branch-name
```

3. **Resolve conflicts** - Edit files to keep desired changes, remove markers

4. **Mark as resolved:**
```bash
git add <resolved-file>
```

5. **Complete merge:**
```bash
git commit -m "Merge branch-name into current-branch

Resolved conflicts in:
- file1.py: Kept authentication logic from both branches
- file2.js: Used incoming changes for API endpoints"
```

### Git History Analysis

**View commit history:**
```bash
# Compact log
git log --oneline --graph --all

# Detailed log with changes
git log -p

# Find commits by author
git log --author="Name"

# Find commits by message
git log --grep="keyword"
```

**Find when bug was introduced:**
```bash
# Binary search through history
git bisect start
git bisect bad                 # Current version is bad
git bisect good <commit>       # Known good commit
# Test each commit git provides
git bisect good/bad            # Mark each test result
git bisect reset               # When done
```

**View file history:**
```bash
# Show changes to specific file
git log -p <file>

# Show who changed each line
git blame <file>
```

## Advanced Operations

For detailed guidance on advanced git operations, see [advanced-operations.md](references/advanced-operations.md).

**Common advanced operations:**

- **Interactive rebase** - Reorder, squash, edit commits
- **Cherry-pick** - Apply specific commits to current branch
- **Reflog** - Recover lost commits
- **Stash** - Temporarily save uncommitted changes
- **Reset** - Undo commits (soft, mixed, hard)
- **Clean** - Remove untracked files

## Guidelines

### Safety Rules

- **Never force push to main/master** - Destroys team's history
- **Never rewrite public history** - Use revert instead
- **Always backup before complex operations** - Create a branch
- **Test before committing** - Run tests, linters
- **Review before pushing** - Check `git diff` and `git log`

### Branch Strategy

- Work on feature branches, not main
- Keep main/master stable and deployable
- Delete branches after merge
- Use descriptive branch names
- Keep feature branches short-lived

### Commit Hygiene

- One logical change per commit
- Test each commit independently
- Write clear, descriptive messages
- Don't commit generated files or secrets
- Use `.gitignore` appropriately

## Common Commands

```bash
# Status and info
git status                      # Show working tree status
git log --oneline --graph      # View commit history
git diff                       # Show unstaged changes
git diff --staged              # Show staged changes

# Basic operations
git add <file>                 # Stage file
git commit -m "message"        # Commit staged changes
git push                       # Push to remote
git pull                       # Fetch and merge from remote

# Branching
git branch                     # List branches
git checkout -b <branch>       # Create and switch to branch
git merge <branch>             # Merge branch into current
git branch -d <branch>         # Delete branch

# Stashing
git stash                      # Save uncommitted changes
git stash list                 # List stashes
git stash pop                  # Apply and remove latest stash
git stash apply                # Apply latest stash (keep it)

# Undoing
git reset HEAD <file>          # Unstage file
git checkout -- <file>         # Discard changes to file
git revert <commit>            # Create new commit undoing changes
git reset --hard <commit>      # Reset to commit (DESTRUCTIVE)
```

## References

- [commit-guidelines.md](references/commit-guidelines.md) - Detailed commit best practices and formatting
- [stacked-prs.md](references/stacked-prs.md) - Comprehensive stacked PR workflow
- [advanced-operations.md](references/advanced-operations.md) - Rebase, cherry-pick, reflog, and more

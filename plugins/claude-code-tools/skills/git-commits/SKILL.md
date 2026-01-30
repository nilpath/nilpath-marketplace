---
name: git-commits
description: Git commit best practices and message formatting guidelines. Use when creating commits, improving commit messages, learning commit conventions, or when user mentions commit messages, commit formatting, or commit guidelines.
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git diff:*), Bash(git log:*), Read
---

# Git Commits

Expert guidance for creating well-formatted, meaningful commits that tell a clear story.

## Current Git Context

- Current git status: !`git status`
- Staged changes: !`git diff --staged`
- Unstaged changes: !`git diff`
- Recent commits: !`git log --oneline -10`
- Current branch: !`git branch --show-current`

## Quick Start

### Create a Well-Formatted Commit

```bash
# Stage specific files
git add src/auth.ts src/types.ts

# Commit with clear message
git commit -m "Add JWT authentication

Implements token-based authentication with refresh tokens.
Includes middleware for protected routes and token validation."
```

**Key Rules:**

- First line: Imperative mood, capitalized, < 50 chars, no period
- Blank line after summary
- Body: Wrap at 72 chars, explain what and why (not how)
- Test before committing

### Conventional Commits Format

```
type(scope): Summary in imperative mood

More detailed explanatory text if needed, wrapped at 72 characters.
Explain the "what" and "why" of the change, not the "how".

Closes #issue-number
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

**Examples:**

```
feat(auth): Add user authentication endpoint
fix(cache): Resolve race condition in invalidation
refactor(api): Extract validation into middleware
perf(db): Add indexes for user dashboard queries
```

## Core Principles

### 1. Commit Related Changes

One logical change per commit. Fixing two bugs? Two separate commits.

```bash
# Good: Separate commits
git add auth.py
git commit -m "Fix authentication token validation"

git add database.py
git commit -m "Add index to users table for performance"

# Bad: Unrelated changes
git add auth.py database.py
git commit -m "Fix various issues"
```

### 2. Commit Often

Small, frequent commits are easier to understand and revert if needed.

**Benefits:**
- Easier to understand each change
- Simpler to revert if needed
- Better collaboration
- Clearer project history

### 3. Test Before Committing

**Pre-commit checklist:**
```bash
# Run tests
pytest                     # Python
npm test                   # JavaScript

# Run linters
pylint src/               # Python
eslint src/               # JavaScript

# Check formatting
black --check src/        # Python
prettier --check src/     # JavaScript

# Review changes
git status                 # What will be committed
git diff --staged          # Actual changes
```

**MAKE SURE NEW CHANGES ARE COVERED BY AUTOMATED TESTS AND ALL TESTS PASS.**

### 4. Don't Commit Half-Done Work

Only commit when a logical component is complete. Use `git stash` for incomplete work:

```bash
# Need to switch branches but work isn't complete
git stash save "WIP: User authentication form validation"
git checkout other-branch

# Come back later
git checkout feature/auth
git stash pop
```

## Good vs Bad Examples

### Feature Implementation

**Good:**
```
Add user profile page

Implements the user profile page with the following:
- Display user information (name, email, avatar)
- Edit profile form with validation
- Upload avatar with image preview
- Update API endpoint integration

Tests included for form validation and API calls.
```

**Bad:**
```
Add stuff
```

### Bug Fix

**Good:**
```
Fix race condition in cache invalidation

The cache was not being properly invalidated when multiple
requests updated the same resource simultaneously, causing
stale data to be served to users.

Changed the invalidation logic to use atomic operations with
a distributed lock to ensure cache consistency.

Fixes #1234
```

**Bad:**
```
Fix bug
```

### Refactoring

**Good:**
```
Extract authentication logic into middleware

Moved authentication checks from individual route handlers
into reusable middleware. This reduces code duplication and
makes authentication logic easier to maintain and test.

No functional changes - all existing tests pass.
```

**Bad:**
```
Update code
```

## Anti-Patterns to Avoid

❌ **Vague messages:** "Fix bug", "Update code", "Changes", "WIP", "asdf"

❌ **Too much in one commit:** "Fix login, add dashboard, update deps, refactor tests"

❌ **Misleading messages:** Commit message says "Fix typo" but actually rewrites authentication system

❌ **No context:** Summary line only, no body when body is needed

❌ **Half-done work:** Committing code that doesn't compile or fails tests

## Testing Requirements

Every commit should include tests and pass all existing tests.

### Test Coverage Expectations

**New features:**
- Unit tests for core logic
- Integration tests for API endpoints
- E2E tests for critical user flows

**Bug fixes:**
- Regression test that fails before the fix
- Test passes after the fix

**Refactoring:**
- All existing tests pass
- No change in functionality

## Templates and References

- **[Detailed guidelines](references/commit-guidelines.md)** - Comprehensive commit best practices
- **[Commit template](templates/commit-message.txt)** - Reusable message template

## Related Skills

- For stacked PR workflows, see `@git-stacked-prs`
- For advanced operations like amend/rebase, see `@git-advanced`

## Philosophy

Git is not a backup system. Each commit should tell a story:
- What changed?
- Why did it change?
- How does it improve the codebase?

**Good commit history enables:**
- Easy code review
- Clear understanding of evolution
- Simple debugging with git bisect
- Confident refactoring
- Team collaboration

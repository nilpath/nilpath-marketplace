# Git Commit Best Practices

Comprehensive guidelines for creating well-structured, meaningful commits.

## Table of Contents

- [Core Principles](#core-principles)
- [Formatting Rules](#formatting-rules)
- [Examples](#examples)
- [Testing Requirements](#testing-requirements)

## Core Principles

### Commit Related Changes

A commit should be a wrapper for related changes. For example, fixing two different bugs should produce two separate commits. Small commits make it easier for other developers to understand the changes and roll them back if something went wrong.

With tools like the staging area and the ability to stage only parts of a file, Git makes it easy to create very granular commits.

**Example:**
```bash
# Good: Separate commits for separate concerns
git add auth.py
git commit -m "Fix authentication token validation"

git add database.py
git commit -m "Add index to users table for performance"

# Bad: Unrelated changes in one commit
git add auth.py database.py
git commit -m "Fix various issues"
```

### Commit Often

Committing often keeps your commits small and helps you commit only related changes. It allows you to share your code more frequently with others, making it easier for everyone to integrate changes regularly and avoid merge conflicts.

Having large commits and sharing them infrequently makes it hard to solve conflicts.

**Benefits:**
- Easier to understand each change
- Simpler to revert if needed
- Better collaboration with team
- Clearer project history

### Don't Commit Half-Done Work

You should only commit code when a logical component is completed.

Split a feature's implementation into logical chunks that can be completed quickly so that you can commit often. If you're tempted to commit just because you need a clean working copy (to check out a branch, pull in changes, etc.), consider using Git's stash feature instead.

**When to commit:**
- Logical unit of work is complete
- Code compiles/runs without errors
- Tests pass
- Feature increment works as intended

**When to stash instead:**
```bash
# Need to switch branches but work isn't complete
git stash save "WIP: User authentication form validation"
git checkout other-branch

# Come back later
git checkout feature/auth
git stash pop
```

### Test Your Code Before You Commit

Resist the temptation to commit something that you "think" is completed. Test it thoroughly to make sure it really is completed and has no side effects.

While committing half-baked things in your local repository only requires you to forgive yourself, having your code tested is even more important when it comes to pushing/sharing your code with others.

**MAKE SURE NEW CHANGES ARE COVERED BY AUTOMATED TESTS AND ALL TESTS PASS.**

**Pre-commit checklist:**
```bash
# Run tests
pytest                     # Python
npm test                   # JavaScript
cargo test                 # Rust

# Run linters
pylint src/               # Python
eslint src/               # JavaScript
cargo clippy              # Rust

# Check formatting
black --check src/        # Python
prettier --check src/     # JavaScript
cargo fmt -- --check      # Rust

# Verify build
make build                # If applicable
```

### Use Branches

Branching is one of Git's most powerful features - quick and easy branching was a central requirement from day one. Branches are the perfect tool to help you avoid mixing up different lines of development.

You should use branches extensively in your development workflows: for new features, bug fixes, experiments, and ideas.

## Formatting Rules

### Summary Line

- **Capitalized, short (50 chars or less)**
- Imperative mood: "Fix bug" not "Fixed bug" or "Fixes bug"
- No period at the end
- Describes what the commit does, not what you did

**Good:**
```
Add user authentication middleware
Fix memory leak in image processor
Update dependencies to latest versions
Remove deprecated API endpoints
```

**Bad:**
```
fixed stuff
WIP
updated some files
changes
```

### Body (If Needed)

- **Wrap at 72 characters** for readability
- **Always leave the second line blank** to separate summary from body
- Explain **what** and **why**, not **how** (code shows how)
- Answer these questions:
  - What was the motivation for the change?
  - How does it differ from the previous implementation?
  - Why was this approach chosen?

### Structure

#### 1. Subject Line (`<type>(<scope>): <summary>`)

The first line must follow this structure: `type(scope): summary`

- **type**: Choose one: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`.
- **scope** (optional): The part of the codebase affected (e.g., `api`, `auth`, `ui`).
- **summary**: A concise description of the change (max 50 characters). Use the imperative mood (e.g., "Add user login" not "Adds user login").

**Example:** `feat(auth): Add user authentication endpoint`

#### 2. Body (Optional)

After the subject line, leave one blank line and then write a more detailed explanation. Explain the "what" and "why" of the change, not the "how". Describe the problem, the solution, and contrast the new behaviour with the old.

**Example:**

```
The application previously lacked a formal authentication process.
This change introduces a /login endpoint that validates user credentials
and returns a JSON Web Token (JWT) for accessing protected routes.
```

#### 3. Footer (Optional)

After another blank line, add any footer information. This is used for referencing issue tracker IDs or declaring breaking changes.

**Example:**

```
Closes #78
BREAKING CHANGE: The /users endpoint now requires authentication.
```

### Full Commit Message Example

```
feat(auth): Add user authentication endpoint

The application previously lacked a formal authentication process.
This change introduces a /login endpoint that validates user credentials
and returns a JSON Web Token (JWT) for accessing protected routes.

Closes #78
```

**Template:** See [commit-message.txt](../templates/commit-message.txt) for a reusable template.

## Examples

### Example 1: Simple Commit (No Body)

```
commit 3114a97ba188895daff4a3d337b2c73855d4632d
Author: Developer Name
Date:   Mon Jun 11 17:16:10 2012 +0100

    Update default policies for KVM guest PIT & RTC timers
```

**When to use:** The change is self-explanatory and doesn't need additional context.

### Example 2: Commit with Bullet Points

```
commit ae878fc8b9761d099a4145617e4a48cbeb390623
Author: Developer Name
Date:   Fri Jun 1 01:44:02 2012 +0000

    Refactor libvirt create calls

     - Minimize duplicated code for create

     - Make wait_for_destroy happen on shutdown instead of undefine

     - Allow for destruction of an instance while leaving the domain
```

**When to use:** Multiple related changes that benefit from being listed separately.

### Example 3: Commit with Detailed Explanation

```
commit 31336b35b4604f70150d0073d77dbf63b9bf7598
Author: Developer Name
Date:   Wed Jun 6 22:45:25 2012 -0400

    Add CPU arch filter scheduler support

    In a mixed environment of running different CPU architectures,
    one would not want to run an ARM instance on a X86_64 host and
    vice versa.

    This scheduler filter option will prevent instances running
    on a host that it is not intended for.

    The libvirt driver queries the guest capabilities of the
    host and stores the guest arches in the permitted_instances_types
    list in the cpu_info dict of the host.

    The Xen equivalent will be done later in another commit.

    The arch filter will compare the instance arch against
    the permitted_instances_types of a host
    and filter out invalid hosts.

    Also adds ARM as a valid arch to the filter.

    The ArchFilter is not turned on by default.
```

**When to use:** Complex changes that require context about motivation, approach, and implementation details.

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

### Pre-commit Commands

```bash
# Python projects
pytest tests/
black --check .
pylint src/

# JavaScript/TypeScript projects
npm test
npm run lint
npm run type-check

# Before committing
git add <files>
git status                    # Review what will be committed
git diff --staged             # Review actual changes
git commit -m "message"
```

## Common Patterns

### Feature Implementation

```
Add user profile page

Implements the user profile page with the following:
- Display user information (name, email, avatar)
- Edit profile form with validation
- Upload avatar with image preview
- Update API endpoint integration

Tests included for form validation and API calls.
```

### Bug Fix

```
Fix race condition in cache invalidation

The cache was not being properly invalidated when multiple
requests updated the same resource simultaneously. This was
causing stale data to be served to users.

Changed the invalidation logic to use atomic operations with
a distributed lock to ensure cache consistency.

Fixes #1234
```

### Refactoring

```
Extract authentication logic into middleware

Moved authentication checks from individual route handlers
into reusable middleware. This reduces code duplication and
makes authentication logic easier to maintain and test.

No functional changes - all existing tests pass.
```

### Performance Improvement

```
Optimize database queries for user dashboard

Reduced dashboard load time from 2.3s to 0.4s by:
- Adding index on user_id and created_at columns
- Using select_related to reduce N+1 queries
- Implementing query result caching for 5 minutes

Benchmarks included in tests/performance/dashboard_test.py
```

## Anti-Patterns to Avoid

### Vague Messages

**Bad:**
```
Fix bug
Update code
Changes
WIP
asdf
```

**Good:**
```
Fix null pointer exception in user service
Update authentication to use JWT tokens
Refactor database connection pooling
```

### Too Much in One Commit

**Bad:**
```
Fix login, add dashboard, update deps, refactor tests
```

**Good:** Split into separate commits:
```
Fix login session timeout issue
Add user dashboard with metrics
Update dependencies to address security vulnerabilities
Refactor authentication tests for better coverage
```

### Commit Messages That Don't Match Changes

**Bad:**
```
# Commit message
Fix typo in README

# Actual changes
- Rewrote entire authentication system
- Added new database tables
- Updated API endpoints
```

**Good:** Commit message accurately reflects all changes or split into multiple commits.

## Version Control Philosophy

Git is not a backup system. When doing version control, commit semantically - don't just cram in files.

Each commit should tell a story:
- What changed?
- Why did it change?
- How does it improve the codebase?

**Good commit history enables:**
- Easy code review
- Clear understanding of evolution
- Simple debugging with git bisect
- Confident refactoring
- Team collaboration

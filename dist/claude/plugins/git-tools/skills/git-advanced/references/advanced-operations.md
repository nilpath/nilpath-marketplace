# Advanced Git Operations

Comprehensive guide to advanced git operations including rebase, cherry-pick, reflog, and more.

## Table of Contents

- [Interactive Rebase](#interactive-rebase)
- [Cherry-Pick](#cherry-pick)
- [Reflog](#reflog)
- [Stash](#stash)
- [Reset](#reset)
- [Clean](#clean)
- [Bisect](#bisect)
- [Amend](#amend)
- [Filter-Branch](#filter-branch)
- [Tags](#tags)

## Interactive Rebase

Interactive rebase allows you to modify commits in many ways: reorder, edit, squash, drop, or reword them.

### Basic Usage

```bash
# Rebase last 3 commits
git rebase -i HEAD~3

# Rebase all commits since branching from main
git rebase -i main

# Rebase commits after specific commit
git rebase -i <commit-hash>
```

### Interactive Rebase Commands

When you run interactive rebase, an editor opens with commands:

```
pick abc1234 Add user authentication
pick def5678 Fix typo in login
pick ghi9012 Add password validation

# Commands:
# p, pick   = use commit
# r, reword = use commit, but edit the commit message
# e, edit   = use commit, but stop for amending
# s, squash = use commit, but meld into previous commit
# f, fixup  = like squash, but discard commit message
# d, drop   = remove commit
```

### Common Scenarios

**Squash multiple commits into one:**

```bash
git rebase -i HEAD~3

# Change:
pick abc1234 Add user authentication
pick def5678 Add tests
pick ghi9012 Fix lint issues

# To:
pick abc1234 Add user authentication
squash def5678 Add tests
squash ghi9012 Fix lint issues

# Save and close editor
# New editor opens to combine commit messages
```

**Reorder commits:**

```bash
git rebase -i HEAD~3

# Change order by moving lines:
pick ghi9012 Fix lint issues
pick abc1234 Add user authentication
pick def5678 Add tests

# Save and close
```

**Edit a commit:**

```bash
git rebase -i HEAD~3

# Change 'pick' to 'edit':
edit abc1234 Add user authentication
pick def5678 Add tests
pick ghi9012 Fix lint issues

# Save and close
# Git stops at the commit, make changes:
git add <files>
git commit --amend
git rebase --continue
```

**Drop a commit:**

```bash
git rebase -i HEAD~3

# Remove the line or change to 'drop':
pick abc1234 Add user authentication
drop def5678 Add tests          # This commit will be removed
pick ghi9012 Fix lint issues

# Save and close
```

### Rebase Conflicts

When conflicts occur during rebase:

```bash
# Git pauses and shows conflicts
git status

# Edit conflicted files, then:
git add <resolved-files>
git rebase --continue

# Or skip this commit:
git rebase --skip

# Or abort entire rebase:
git rebase --abort
```

### Safety Tips

- **Never rebase commits that have been pushed to shared branches**
- Always work on feature branches
- Create a backup branch before complex rebases: `git branch backup-branch`
- Use `--force-with-lease` instead of `--force` when pushing

## Cherry-Pick

Apply specific commits from one branch to another without merging.

### Basic Usage

```bash
# Apply single commit to current branch
git cherry-pick <commit-hash>

# Apply multiple commits
git cherry-pick <commit-1> <commit-2> <commit-3>

# Apply range of commits (exclusive of first, inclusive of last)
git cherry-pick <commit-1>..<commit-n>

# Apply range (inclusive of both)
git cherry-pick <commit-1>^..<commit-n>
```

### Common Scenarios

**Applying a hotfix to multiple branches:**

```bash
# Fix bug on main
git checkout main
git commit -m "Fix critical security bug"  # Creates abc1234

# Apply to release branch
git checkout release-1.0
git cherry-pick abc1234

# Apply to another release
git checkout release-2.0
git cherry-pick abc1234
```

**Pulling specific features from another branch:**

```bash
# Feature branch has 5 commits, but you only want commit 3
git log feature-branch  # Find commit hash for commit 3

git checkout main
git cherry-pick def5678  # Apply commit 3 only
```

### Cherry-Pick Options

```bash
# Cherry-pick but don't commit (stage changes only)
git cherry-pick -n <commit>
git cherry-pick --no-commit <commit>

# Edit commit message during cherry-pick
git cherry-pick -e <commit>
git cherry-pick --edit <commit>

# Add "cherry picked from" note to commit message
git cherry-pick -x <commit>
```

### Handling Conflicts

```bash
git cherry-pick abc1234

# If conflicts:
# Edit conflicted files
git add <resolved-files>
git cherry-pick --continue

# Or abort:
git cherry-pick --abort
```

## Reflog

Reflog (reference log) records all changes to branch tips and HEAD. It's your safety net for recovering "lost" commits.

### Viewing Reflog

```bash
# Show reflog for HEAD
git reflog

# Show reflog for specific branch
git reflog show feature-branch

# Show reflog with dates
git reflog --date=relative

# Show detailed reflog
git reflog show --all
```

### Example Output

```
abc1234 HEAD@{0}: commit: Add user authentication
def5678 HEAD@{1}: rebase finished
ghi9012 HEAD@{2}: checkout: moving from main to feature
jkl3456 HEAD@{3}: pull: Fast-forward
```

### Recovering Lost Commits

**Scenario 1: Accidentally reset:**

```bash
# You ran: git reset --hard HEAD~3
# And lost commits!

# View reflog to find lost commits
git reflog

# Find the commit before reset
abc1234 HEAD@{0}: reset: moving to HEAD~3
def5678 HEAD@{1}: commit: Important feature  # This is what we lost!

# Restore to that commit
git reset --hard def5678
# or
git reset --hard HEAD@{1}
```

**Scenario 2: Deleted branch with unmerged commits:**

```bash
# You deleted feature-branch
git branch -D feature-branch

# Find the last commit on that branch
git reflog show feature-branch

# Recreate branch at that commit
git branch feature-branch <commit-hash>
```

**Scenario 3: Bad rebase:**

```bash
# Rebase went wrong
git reflog

# Find commit before rebase started
git reset --hard HEAD@{5}
```

### Reflog Expiration

- Reflog entries expire after 90 days by default
- Unreachable commits expire after 30 days
- Configure with: `git config gc.reflogExpire "120 days"`

## Stash

Temporarily save uncommitted changes without committing them.

### Basic Stash Commands

```bash
# Stash changes (tracked files only)
git stash

# Stash with message
git stash save "WIP: user authentication"
git stash push -m "WIP: user authentication"

# Stash including untracked files
git stash -u
git stash --include-untracked

# Stash including untracked and ignored files
git stash -a
git stash --all

# List stashes
git stash list

# Apply most recent stash (keep in stash list)
git stash apply

# Apply and remove most recent stash
git stash pop

# Apply specific stash
git stash apply stash@{2}

# Remove specific stash
git stash drop stash@{1}

# Remove all stashes
git stash clear
```

### Advanced Stash Operations

**Create branch from stash:**

```bash
# Create new branch with stashed changes
git stash branch new-branch-name stash@{1}
```

**Stash specific files:**

```bash
# Stash only specific files
git stash push -m "Stash specific files" file1.py file2.py
```

**View stash contents:**

```bash
# Show changes in most recent stash
git stash show

# Show detailed diff
git stash show -p

# Show specific stash
git stash show -p stash@{2}
```

**Interactive stashing:**

```bash
# Choose which changes to stash interactively
git stash -p
git stash --patch
```

### Common Workflow

```bash
# Working on feature but need to switch branches
git stash save "WIP: Half-done authentication"

# Switch to other branch and work
git checkout hotfix-branch
# ... make hotfix ...
git commit -m "Fix critical bug"

# Return to feature work
git checkout feature-branch
git stash pop

# If conflicts after pop:
# Resolve conflicts, then:
git restore --staged <file>  # Unstage if needed
# Stash is automatically dropped if pop succeeds
```

## Reset

Move branch pointer to different commit, optionally modifying staging area and working directory.

### Reset Modes

**Soft reset** - Move HEAD, keep staging and working directory:
```bash
git reset --soft HEAD~1

# Use case: Undo last commit but keep all changes staged
# Perfect for: Fixing commit message or adding more changes
```

**Mixed reset (default)** - Move HEAD, update staging, keep working directory:
```bash
git reset HEAD~1
git reset --mixed HEAD~1

# Use case: Undo last commit and unstage changes
# Perfect for: Re-organizing what goes into commits
```

**Hard reset** - Move HEAD, update staging and working directory:
```bash
git reset --hard HEAD~1

# Use case: Completely discard commits and all changes
# WARNING: Destructive! Changes are lost!
```

### Common Scenarios

**Undo last commit, keep changes:**

```bash
git reset --soft HEAD~1
# Changes are still staged, ready to commit again
```

**Undo last commit, unstage changes:**

```bash
git reset HEAD~1
# Changes are in working directory but not staged
```

**Discard all local changes:**

```bash
git reset --hard HEAD
# Working directory matches last commit
```

**Undo multiple commits:**

```bash
# Undo last 3 commits, keep changes
git reset --soft HEAD~3

# Discard last 3 commits
git reset --hard HEAD~3
```

**Reset to specific commit:**

```bash
git reset --hard abc1234
```

**Reset single file:**

```bash
# Unstage file (from staging to working directory)
git reset HEAD <file>

# Discard changes to file
git restore <file>
git checkout -- <file>  # Old syntax
```

### Reset vs Revert

**Reset** - Moves branch pointer, rewrites history:
```bash
git reset --hard HEAD~1
# Removes commit from history
# Use for: Local commits not yet pushed
```

**Revert** - Creates new commit that undoes changes:
```bash
git revert HEAD
# Keeps commit in history, adds new "undo" commit
# Use for: Commits already pushed to shared branches
```

## Clean

Remove untracked files and directories from working directory.

### Basic Clean Commands

```bash
# Dry run - show what would be deleted
git clean -n

# Delete untracked files
git clean -f

# Delete untracked files and directories
git clean -fd

# Delete untracked and ignored files
git clean -fx

# Interactive clean
git clean -i
```

### Safety Options

```bash
# Always run dry run first!
git clean -n

# Interactive mode for careful selection
git clean -i

# What would you like to do?
# 1: clean                2: filter by pattern
# 3: select by numbers    4: ask each
# 5: quit                 6: help
```

### Common Scenarios

**Clean up after build:**

```bash
# Remove all build artifacts (including ignored files)
git clean -fdx
```

**Remove untracked files but keep directories:**

```bash
git clean -f
```

**Clean specific directory:**

```bash
git clean -fd src/temp/
```

## Bisect

Binary search through commit history to find when a bug was introduced.

### Basic Workflow

```bash
# Start bisect
git bisect start

# Mark current commit as bad
git bisect bad

# Mark a known good commit
git bisect good abc1234

# Git checks out middle commit
# Test if bug exists:

# If bug exists:
git bisect bad

# If bug doesn't exist:
git bisect good

# Repeat until git finds the culprit commit

# End bisect
git bisect reset
```

### Example Session

```bash
# Current commit has bug, commit from 2 weeks ago was fine
git bisect start
git bisect bad HEAD
git bisect good abc1234

# Git checks out commit: def5678
# Test the application...
# Bug still exists:
git bisect bad

# Git checks out commit: ghi9012
# Test the application...
# Bug doesn't exist:
git bisect good

# Git narrows it down: "xyz7890 is the first bad commit"

# View the problematic commit
git show xyz7890

# End bisect
git bisect reset
```

### Automated Bisect

Run a script to automatically test each commit:

```bash
# Script that exits with 0 if good, non-zero if bad
# Example: run_tests.sh

git bisect start
git bisect bad HEAD
git bisect good abc1234

# Let git automatically bisect using the script
git bisect run ./run_tests.sh

# Git will find the bad commit automatically
git bisect reset
```

### Bisect with Skip

If a commit can't be tested (won't compile, etc.):

```bash
git bisect skip
```

### Visualizing Bisect

```bash
# See bisect log
git bisect log

# Visualize bisect progress
git bisect visualize
git bisect view
```

## Amend

Modify the most recent commit.

### Basic Amend

```bash
# Add changes to last commit
git add <files>
git commit --amend

# Keep same commit message
git commit --amend --no-edit

# Only change commit message
git commit --amend -m "New message"
```

### Common Scenarios

**Forgot to add a file:**

```bash
git commit -m "Add user authentication"
# Oops! Forgot to add auth.test.py

git add auth.test.py
git commit --amend --no-edit
```

**Fix typo in commit message:**

```bash
git commit -m "Add user authntication"  # Typo!

git commit --amend -m "Add user authentication"
```

**Add more changes to last commit:**

```bash
# Made commit but realized need more changes
git add <more-files>
git commit --amend

# Edit message in editor, or:
git commit --amend --no-edit
```

### Safety Warning

**Never amend commits that have been pushed to shared branches!**

```bash
# If you've already pushed:
git push

# Then amended:
git commit --amend

# You'll need force push:
git push --force-with-lease

# This rewrites history and can cause problems for collaborators!
```

## Filter-Branch

Rewrite git history (use with extreme caution).

### ⚠️ Warning

Modern alternative: Use `git filter-repo` instead of `git filter-branch`.

Install: `pip install git-filter-repo`

### Common Scenarios

**Remove file from entire history:**

```bash
# Using filter-repo (recommended)
git filter-repo --path sensitive-file.txt --invert-paths

# Old method (filter-branch)
git filter-branch --tree-filter 'rm -f sensitive-file.txt' HEAD
```

**Remove directory from history:**

```bash
git filter-repo --path old-dir/ --invert-paths
```

**Change author information:**

```bash
# Using filter-repo
git filter-repo --commit-callback '
  if commit.author_email == b"old@example.com":
    commit.author_email = b"new@example.com"
    commit.committer_email = b"new@example.com"
'
```

**Extract subdirectory as new repository:**

```bash
git filter-repo --subdirectory-filter path/to/subdirectory
```

### Safety Checklist

Before filter-branch/filter-repo:

- [ ] Backup repository: `git clone --mirror repo backup-repo`
- [ ] Coordinate with team - this rewrites history!
- [ ] All team members must re-clone after operation
- [ ] Consider if this is really necessary

## Tags

Mark specific points in history, typically for releases.

### Creating Tags

**Lightweight tag:**
```bash
git tag v1.0.0
```

**Annotated tag (recommended):**
```bash
git tag -a v1.0.0 -m "Release version 1.0.0"
```

**Tag specific commit:**
```bash
git tag -a v1.0.0 <commit-hash> -m "Release version 1.0.0"
```

### Listing Tags

```bash
# List all tags
git tag

# List tags matching pattern
git tag -l "v1.0.*"

# Show tag details
git show v1.0.0
```

### Pushing Tags

```bash
# Push specific tag
git push origin v1.0.0

# Push all tags
git push --tags

# Push only annotated tags
git push --follow-tags
```

### Deleting Tags

```bash
# Delete local tag
git tag -d v1.0.0

# Delete remote tag
git push origin :refs/tags/v1.0.0
# or
git push origin --delete v1.0.0
```

### Checking Out Tags

```bash
# View code at tag (detached HEAD)
git checkout v1.0.0

# Create branch from tag
git checkout -b hotfix-1.0.1 v1.0.0
```

### Semantic Versioning Tags

```bash
# Format: vMAJOR.MINOR.PATCH

git tag -a v1.0.0 -m "Initial release"        # Major release
git tag -a v1.1.0 -m "Add new features"       # Minor update
git tag -a v1.1.1 -m "Fix critical bug"       # Patch
git tag -a v2.0.0 -m "Breaking changes"       # New major version
```

## Best Practices Summary

### Do's

✅ Create backup branches before complex operations
✅ Test after each operation
✅ Use `--force-with-lease` instead of `--force`
✅ Run dry-run commands first (`-n` flag)
✅ Keep reflog enabled (default)
✅ Use interactive mode for careful operations
✅ Document why you're doing complex operations

### Don'ts

❌ Never rewrite public/shared history
❌ Never use `git push --force` on main branches
❌ Never run destructive commands without backup
❌ Never filter-branch without team coordination
❌ Never assume you can't recover (check reflog first)
❌ Never skip testing after rebasing or cherry-picking

### Recovery Checklist

If something goes wrong:

1. **Don't panic** - Git rarely loses data permanently
2. **Check reflog** - `git reflog`
3. **Find the good commit** - Look for commit before mistake
4. **Reset to it** - `git reset --hard <commit>`
5. **If deleted branch** - `git branch branch-name <commit>`
6. **If still stuck** - Check `.git/` directory for loose objects

### Learning Resources

Practice these commands safely:

1. Create a test repository
2. Make several commits
3. Practice rebasing, resetting, cherry-picking
4. Intentionally "break" things and recover
5. Use `git log --graph --all --decorate` to visualize

**Remember:** Most git operations are reversible with reflog. The main exceptions are:
- Uncommitted changes when running `git reset --hard`
- Running `git clean -f` on untracked files
- Operations on expired reflog entries

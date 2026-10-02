---
name: git-advanced
description: Advanced git operations (rebase, cherry-pick, reflog, stash, reset, clean), analysis tools (bisect, blame, history), and command reference. Use for complex git tasks, recovery operations, or when user mentions rebase, cherry-pick, reflog, stash, reset, bisect, or needs git command reference.
allowed-tools: Bash(git:*), Read
---

# Git Advanced Operations

Expert guidance for advanced git operations, history analysis, recovery, and command reference.

## Current Git Context

- Current git status: !`git status`
- Current branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`
- Reflog (recent operations): !`git reflog -10`
- All branches: !`git branch -a`

## Quick Navigation

### Advanced Operations
- [Interactive Rebase](#interactive-rebase) - Reorder, squash, edit commits
- [Cherry-Pick](#cherry-pick) - Apply specific commits
- [Stash](#stash) - Save uncommitted changes temporarily
- [Reset](#reset) - Undo commits (soft, mixed, hard)
- [Clean](#clean) - Remove untracked files
- [Amend](#amend) - Modify last commit

### Analysis & Debugging
- [Reflog](#reflog) - Recover lost commits
- [Bisect](#bisect) - Find bug-introducing commits
- [Blame](#blame) - See who changed each line
- [History Search](#history-search) - Search git history

### Recovery
- [Common Recovery Scenarios](#common-recovery-scenarios)

### References
- [Command Reference](references/common-commands.md) - Quick command lookup
- [Detailed Operations](references/advanced-operations.md) - Comprehensive guide

## Interactive Rebase

Modify commits: reorder, edit, squash, drop, or reword.

**Basic usage:**
```bash
# Rebase last 3 commits
git rebase -i HEAD~3

# Rebase since branching from main
git rebase -i main
```

**Interactive commands:**
```
pick abc1234 Add user authentication
reword def5678 Fix typo in login        # Edit message
squash ghi9012 Add password validation  # Combine with previous
drop jkl3456 Debug logging              # Remove commit

# p/pick, r/reword, e/edit, s/squash, f/fixup, d/drop
```

**Example - Squash last 3 commits:**
```bash
git rebase -i HEAD~3
# Change last 2 "pick" to "squash", save, edit combined message
```

**Safety:**
- ⚠️ Never rebase commits pushed to shared branches
- Create backup branch before complex rebases
- Use `git rebase --abort` if things go wrong

For detailed examples, see [advanced-operations.md](references/advanced-operations.md#interactive-rebase).

## Cherry-Pick

Apply specific commits from one branch to another.

**Basic usage:**
```bash
# Apply single commit
git cherry-pick <commit-hash>

# Apply multiple commits
git cherry-pick <commit1> <commit2>

# Apply range of commits
git cherry-pick <commit1>^..<commit2>
```

**Handle conflicts:**
```bash
git status                    # Identify conflicts
# Edit and resolve conflicts
git add <resolved-files>
git cherry-pick --continue    # Or: git cherry-pick --abort
```

**Use cases:** Apply bug fix across branches, port features, extract specific commits.

For detailed examples, see [advanced-operations.md](references/advanced-operations.md#cherry-pick).

## Reflog

Your safety net - tracks all ref updates (commits, resets, checkouts, etc.).

**Basic usage:**
```bash
# View reflog
git reflog

# View reflog for specific branch
git reflog show feature-branch
```

**Recover lost commit:**
```bash
git reflog                       # Find lost commit (e.g., HEAD@{2})
git cherry-pick HEAD@{2}         # Recover it
# Or: git branch recovered HEAD@{2}
```

Reflog is your recovery tool for undoing resets, recovering deleted branches, and finding lost commits. See [Common Recovery Scenarios](#common-recovery-scenarios) below.

## Stash

Save uncommitted changes temporarily without committing.

**Basic usage:**
```bash
git stash                              # Stash all changes
git stash save "WIP: User auth"        # Stash with message
git stash list                         # List stashes
git stash pop                          # Apply and remove stash
git stash apply stash@{2}              # Apply specific stash
```

**Advanced:**
```bash
git stash -u                           # Include untracked files
git stash --keep-index                 # Stash only unstaged changes
git stash branch new-branch-name       # Create branch from stash
git stash drop stash@{1}               # Drop specific stash
```

**Use cases:** Switch branches with uncommitted work, try experimental changes, clean working directory temporarily.

For detailed examples, see [advanced-operations.md](references/advanced-operations.md#stash).

## Reset

Move branch pointer and optionally modify staging area and working directory.

**Reset modes:**
```bash
git reset --soft HEAD~1     # Move HEAD, keep changes staged
git reset HEAD~1            # Move HEAD, unstage changes, keep in working dir (default)
git reset --hard HEAD~1     # Move HEAD, discard all changes
```

**Common use cases:**
```bash
git reset --soft HEAD~1     # Undo last commit, keep changes staged
git reset                   # Unstage all files
git reset --hard HEAD       # Discard all local changes
git reset --hard <commit>   # Move branch to specific commit
```

**Safety:**
- ⚠️ `--hard` discards work permanently (unless you use reflog)
- Never reset commits pushed to shared branches
- Use reflog to recover from bad resets

For detailed examples, see [advanced-operations.md](references/advanced-operations.md#reset).

## Clean

Remove untracked files from working directory.

**Basic usage:**
```bash
git clean -n       # Dry run (see what would be deleted)
git clean -f       # Delete untracked files
git clean -fd      # Delete untracked files and directories
git clean -fdx     # Include ignored files
```

**Safety:**
- ⚠️ Deleted files cannot be recovered
- Always run `-n` (dry run) first
- Be careful with `-x` (deletes ignored files like dependencies)

## Bisect

Binary search to find commit that introduced a bug.

**Basic workflow:**
```bash
git bisect start
git bisect bad                    # Mark current as bad
git bisect good <commit-hash>     # Mark known good commit
# Git checks out middle commit - test the code
git bisect good                   # Or: git bisect bad
# Repeat until bug found
git bisect reset                  # End bisect
```

**Automated bisect:**
```bash
git bisect start HEAD v1.0
git bisect run ./test_script.sh   # Script exits 0 if good, non-zero if bad
```

For detailed examples, see [advanced-operations.md](references/advanced-operations.md#bisect).

## Amend

Modify the last commit.

**Basic usage:**
```bash
git commit --amend -m "New message"        # Modify message
git add forgotten-file.txt                 # Add more changes
git commit --amend --no-edit               # Amend without changing message
```

**Safety:**
- ⚠️ Never amend commits that have been pushed
- Creates new commit (changes hash)
- If already pushed, requires force push (dangerous on shared branches)

## Blame

See who last modified each line of a file.

**Basic usage:**
```bash
git blame <file>                # Blame entire file
git blame -L 10,20 <file>       # Blame specific lines
git blame -e <file>             # Show email instead of name
git blame -w <file>             # Ignore whitespace changes
```

**Use cases:** Find who to ask about code, understand when/why code changed, track down bug introduction.

## History Search

Find commits by various criteria.

**Search commit messages:**
```bash
git log --grep="bug fix"                              # Search messages
git log --grep="bug fix" -i                           # Case insensitive
git log --grep="bug" --grep="fix" --all-match        # Multiple patterns
```

**Search code content:**
```bash
git log -S "function_name"                            # Added/removed text
git log -G "regex_pattern"                            # Regex pattern
git log -p -S "function_name"                         # Show patches
```

**Filter by author/date:**
```bash
git log --author="John Doe"                           # By author
git log --since="2 weeks ago"                         # By date
git log --after="2024-01-01" --before="2024-02-01"   # Date range
git log --author="John" --since="1 month ago" --grep="fix"  # Combined
```

For detailed examples, see [advanced-operations.md](references/advanced-operations.md#history-search).

## Common Recovery Scenarios

Use reflog to recover from mistakes:

**Recover lost commit:**
```bash
git reflog                       # Find lost commit
git cherry-pick HEAD@{5}         # Or: git branch recovered HEAD@{5}
```

**Undo accidental reset:**
```bash
git reflog                       # Find previous HEAD
git reset --hard HEAD@{1}        # Reset back
```

**Restore deleted branch:**
```bash
git reflog                       # Find last commit on deleted branch
git branch recovered-branch <commit-hash>
```

**Step-by-step recovery:**
1. Find the lost commit: `git reflog`
2. Verify it's the right one: `git show HEAD@{5}`
3. Recover it: `git cherry-pick HEAD@{5}` or `git reset --hard HEAD@{5}` or `git branch recovered HEAD@{5}`

For detailed recovery procedures, see [advanced-operations.md](references/advanced-operations.md#recovery).

## Safety Best Practices

**Before risky operations:**
```bash
git branch backup-$(date +%Y%m%d)    # Create backup branch
git reflog                           # Verify reflog is working
git clean -n                         # Dry run for clean operations
```

**Golden rules:**
- ⚠️ Never force push to main/master
- ⚠️ Never rewrite public history (pushed commits)
- ✅ Always use `--force-with-lease` instead of `--force`
- ✅ Create backup branches before complex operations
- ✅ Test commands on non-critical branches first
- ✅ Communicate with team before shared branch operations

## Command Reference

See [references/common-commands.md](references/common-commands.md) for complete command reference including basic operations, branching, merging, remote operations, inspection, and all flags.

## Detailed Documentation

See [references/advanced-operations.md](references/advanced-operations.md) for in-depth examples, advanced scenarios, troubleshooting guides, and complete coverage of all operations.

## Related Skills

- For commit best practices, see `@git-commits`
- For stacked PR workflows, see `@git-stacked-prs`

## Quick Reference

**Most used advanced commands:**
```bash
git reflog                      # View history (recovery)
git stash                       # Save work temporarily
git rebase -i HEAD~3            # Interactive rebase
git cherry-pick <commit>        # Apply specific commit
git reset --soft HEAD~1         # Undo commit, keep changes
git bisect start                # Find bug-introducing commit
git clean -n                    # Dry run cleanup
git commit --amend              # Modify last commit
git log --grep="pattern"        # Search history
git blame <file>                # See who changed lines
```

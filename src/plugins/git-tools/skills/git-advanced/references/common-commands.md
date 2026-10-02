# Common Git Commands

Quick reference for frequently used git commands.

## Status and Info

```bash
git status                      # Show working tree status
git log --oneline --graph      # View commit history
git log --all --decorate       # View all branches
git diff                       # Show unstaged changes
git diff --staged              # Show staged changes
git diff main..feature         # Compare branches
git show <commit>              # Show commit details
```

## Basic Operations

```bash
git add <file>                 # Stage specific file
git add .                      # Stage all changes
git add -p                     # Stage interactively
git commit -m "message"        # Commit with message
git commit --amend             # Amend last commit
git push                       # Push to remote
git push -u origin <branch>    # Push and set upstream
git pull                       # Fetch and merge from remote
git fetch                      # Fetch without merging
```

## Branching

```bash
git branch                     # List local branches
git branch -a                  # List all branches
git branch <name>              # Create branch
git checkout <branch>          # Switch to branch
git checkout -b <branch>       # Create and switch
git switch <branch>            # Switch branch (modern)
git switch -c <branch>         # Create and switch (modern)
git merge <branch>             # Merge branch into current
git branch -d <branch>         # Delete merged branch
git branch -D <branch>         # Force delete branch
```

## Stashing

```bash
git stash                      # Save uncommitted changes
git stash save "message"       # Stash with message
git stash list                 # List stashes
git stash show                 # Show latest stash
git stash show -p              # Show latest stash with diff
git stash pop                  # Apply and remove latest stash
git stash apply                # Apply latest stash (keep it)
git stash apply stash@{2}      # Apply specific stash
git stash drop                 # Delete latest stash
git stash clear                # Delete all stashes
```

## Undoing Changes

```bash
git restore <file>             # Discard changes (modern)
git checkout -- <file>         # Discard changes (old)
git restore --staged <file>    # Unstage file (modern)
git reset HEAD <file>          # Unstage file (old)
git revert <commit>            # Create new commit undoing changes
git reset --soft HEAD~1        # Undo commit, keep changes staged
git reset --mixed HEAD~1       # Undo commit, unstage changes
git reset --hard HEAD~1        # Undo commit, discard changes (DANGEROUS)
git clean -n                   # Show what would be removed
git clean -f                   # Remove untracked files
git clean -fd                  # Remove untracked files and directories
```

## History and Search

```bash
git log                        # View commit history
git log --oneline              # Compact log
git log -p                     # Show diffs in log
git log --author="Name"        # Filter by author
git log --grep="keyword"       # Filter by commit message
git log --since="2 weeks ago"  # Filter by date
git log <file>                 # History of specific file
git log -p <file>              # History with diffs for file
git blame <file>               # Show who changed each line
git show <commit>:<file>       # Show file at specific commit
```

## Remote Operations

```bash
git remote -v                  # List remotes
git remote add <name> <url>    # Add remote
git remote remove <name>       # Remove remote
git remote set-url <name> <url> # Change remote URL
git fetch origin               # Fetch from origin
git fetch --all                # Fetch from all remotes
git push origin <branch>       # Push branch to remote
git push --all                 # Push all branches
git push --tags                # Push all tags
git push --force-with-lease    # Safe force push
git pull origin <branch>       # Pull specific branch
git pull --rebase              # Pull and rebase instead of merge
```

## Rebasing

```bash
git rebase <branch>            # Rebase current onto branch
git rebase -i HEAD~3           # Interactive rebase last 3 commits
git rebase --continue          # Continue after resolving conflicts
git rebase --skip              # Skip current commit
git rebase --abort             # Cancel rebase
git pull --rebase              # Fetch and rebase
```

## Cherry-pick

```bash
git cherry-pick <commit>       # Apply commit to current branch
git cherry-pick <commit1> <commit2>  # Apply multiple commits
git cherry-pick --continue     # Continue after conflicts
git cherry-pick --abort        # Cancel cherry-pick
```

## Tags

```bash
git tag                        # List tags
git tag <name>                 # Create lightweight tag
git tag -a <name> -m "msg"     # Create annotated tag
git tag -d <name>              # Delete local tag
git push origin <tag>          # Push specific tag
git push origin --tags         # Push all tags
git push origin :refs/tags/<tag>  # Delete remote tag
```

## Submodules

```bash
git submodule add <url> <path> # Add submodule
git submodule init             # Initialize submodules
git submodule update           # Update submodules
git submodule update --remote  # Update to latest remote
git clone --recursive <url>    # Clone with submodules
```

## Advanced

```bash
git reflog                     # Show reference log
git fsck --lost-found          # Find dangling commits
git bisect start               # Start binary search
git bisect bad                 # Mark as bad
git bisect good <commit>       # Mark as good
git bisect reset               # End bisect
git worktree add <path> <branch>  # Create linked working tree
git worktree list              # List worktrees
git archive --format=zip HEAD  # Create archive of HEAD
```

## Configuration

```bash
git config --global user.name "Name"        # Set name
git config --global user.email "email"      # Set email
git config --global core.editor "vim"       # Set editor
git config --list                           # List all config
git config --global alias.st status         # Create alias
git config --global pull.rebase true        # Always rebase on pull
```

## Useful Aliases

Add to `.gitconfig`:

```ini
[alias]
  st = status
  co = checkout
  br = branch
  ci = commit
  unstage = reset HEAD --
  last = log -1 HEAD
  visual = log --oneline --graph --all --decorate
  amend = commit --amend --no-edit
  undo = reset --soft HEAD~1
  aliases = config --get-regexp alias
```

## Flags Reference

### Common Flags

- `-a` - All (applies to add, branch, log, etc.)
- `-b` - Create branch (checkout, switch)
- `-d` - Delete
- `-D` - Force delete
- `-f` - Force
- `-m` - Message (commit, tag)
- `-n` - Dry run (shows what would happen)
- `-p` - Patch mode (interactive)
- `-u` - Set upstream (push)
- `-v` - Verbose
- `--all` - All branches/remotes
- `--amend` - Modify last commit
- `--hard` - Discard changes (dangerous)
- `--soft` - Keep changes
- `--mixed` - Unstage changes (default reset)

### Dangerous Flags

Use with caution:

- `--force` - Force push (use --force-with-lease instead)
- `--hard` - Discard changes permanently
- `-D` - Force delete
- `clean -f` - Remove files permanently

# Draft pull request delivery

Feature and bug-fix runs end here, after the change is verified and reviewed. Investigation runs never reach this step.

## Before you start

- Honor the user's stated limits. "No push", "don't open a PR", or "local only" means stop after the local commits and report the branch.
- Do not publish an unverified change as if it passed. If verification is incomplete and the user explicitly asked for a work-in-progress draft, publish it and state every gap in the body. Otherwise stop and report what is unverified.

## 1. Branch

Do this before the first commit of the run, not at the end. Commits made on the base branch would stay on the local base branch even after you switch.

1. Determine the base branch: the branch the user named, else the repository default (`gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`, or `git symbolic-ref --short refs/remotes/origin/HEAD`). If it is ambiguous, ask the user.
2. If you are on the base branch, create a feature branch from the current HEAD: `git switch -c nstack/<short-slug>`. Uncommitted work moves with you; do not stash or discard it.
3. If you are already on a feature branch, inspect it first (`git status`, `git log --oneline <base>..HEAD`, and any open pull request for it). Do not rewrite commits that are already pushed.

## 2. Commit

- Stage only the files this task changed, by explicit path. Never `git add -A`, `git add .`, or `git commit -a`.
- Leave unrelated changes in the working tree untouched and mention them in the report.
- Prefer small, ordered commits, each verified before the next. For a bug fix with a cheap test path, commit the failing test before the fix.
- Never use `--force`, `--force-with-lease`, `reset --hard`, or history rewrites on shared branches.

## 3. Body

Write the pull request body to a temporary file outside the repository. Include:

- **Summary.** What changed and for whom.
- **Design.** The chosen shape and why; alternatives considered, when `architect` or `candidate-graft` ran.
- **Verification.** The commands you ran and their decisive output. For a bug fix, the failing-then-passing reproduction.
- **Review.** The `review-panel` outcome: what was acted on, and what was considered or dismissed with reasons.
- **Not verified.** Anything you could not check, and why. Write "None" only when that is true.
- **Model selection.** Name the models that ran the work, as the client reported them.

## 4. Publish

Run the bundled publisher from the repository root:

```bash
python3 "<nstack-flow skill directory>/scripts/publish_draft.py" --base <base> --title "<title>" --body-file <body file>
```

The publisher is `scripts/publish_draft.py` inside the `nstack-flow` skill directory, the parent of the directory containing this file. Use its absolute path.

It pushes without force, reuses an existing open pull request for the branch instead of creating another, creates new pull requests as **drafts** only, and verifies that the pull request's head matches your local HEAD. It never marks a pull request ready, merges, enables auto-merge, or watches CI. Do not do any of those yourself either.

- `"ok": true` gives the verified URL, draft state, and head SHA. Report them.
- `"ok": false` gives an error code, message, and repair. Report the blocked result honestly; your local commits remain in place. Never substitute a local result for the promised draft without saying so.
- An existing pull request that is not a draft stays as it is; report its state.

Delete the temporary body file afterwards.

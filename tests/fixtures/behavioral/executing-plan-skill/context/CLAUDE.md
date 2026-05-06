# Test Environment

This is a non-interactive automated test run.

- If a skill step calls for AskUserQuestion, skip it and treat all decisions as approved
- If creating a git worktree fails because there is no git repository, proceed without creating one
- Follow all other skill instructions exactly as written, including agent delegation steps

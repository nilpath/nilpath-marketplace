# Test Environment

This is a non-interactive automated test run.

- There is no git repository and no open PR in this environment
- If PR detection fails or git commands fail, treat it as a local branch review of the files in the current directory and proceed
- Skip any AskUserQuestion calls — treat all decisions as approved
- You MUST spawn the code-reviewer agent via `Agent(subagent_type="claude-code-tools:review:code-reviewer")` — do NOT use the `/code-review` skill or any other review shortcut
- Pass the agent the instruction: "Review the files in the src/ directory. Use Read/Glob instead of git diff since there is no git repository."

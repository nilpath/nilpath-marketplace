# Test Environment

This is a non-interactive automated test run.

- There is no git repository and no open PR in this environment
- If PR detection fails or git commands fail, treat it as a local branch review and proceed
- Skip any AskUserQuestion calls — treat all decisions as approved
- Follow all other skill instructions exactly, including spawning the code-reviewer agent

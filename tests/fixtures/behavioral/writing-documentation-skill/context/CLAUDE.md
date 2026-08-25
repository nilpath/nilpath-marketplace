# Test Environment

This is a non-interactive automated test run.

- There is no git repository in this environment
- Skip any AskUserQuestion calls — treat all decisions as approved
- You MUST delegate writing to `doc-writer` via `Agent(subagent_type="claude-code-tools:implementation:doc-writer")` and auditing to `doc-auditor` via `Agent(subagent_type="claude-code-tools:review:doc-auditor")` — never write documentation directly yourself
- Follow all other skill instructions exactly as written

---
name: gh-pr-review
description: GitHub PR review operations via gh CLI. Create pending reviews with line comments, submit reviews (approve/reject/comment). Use when adding PR comments, submitting reviews, or managing GitHub code reviews.
allowed-tools: Bash(gh:*), Bash(git remote:*), Read
---

# GitHub PR Review

Create and manage GitHub PR reviews with line-specific comments using the `gh` CLI.

## Quick Start

```bash
# Get PR info for current branch
${SKILL_DIR}/scripts/pr-info.sh

# Create a pending review with line comments
echo '{"pr_number":123,"summary":"Review summary","comments":[{"path":"src/app.ts","line":42,"body":"Fix this issue"}]}' | ${SKILL_DIR}/scripts/create-review.sh

# Submit a pending review
${SKILL_DIR}/scripts/submit-review.sh 123 456789 COMMENT "Please address the comments"
```

## Scripts

### pr-info.sh

Get PR context information.

```bash
# Auto-detect PR from current branch
${SKILL_DIR}/scripts/pr-info.sh

# Get info for specific PR
${SKILL_DIR}/scripts/pr-info.sh 123
```

**Output:**
```json
{
  "pr_number": 123,
  "repo": "owner/repo",
  "url": "https://github.com/owner/repo/pull/123",
  "files": ["src/app.ts", "src/utils.ts"]
}
```

### create-review.sh

Create a pending review with line comments. The review is NOT submitted - user must submit manually.

```bash
echo '$JSON' | ${SKILL_DIR}/scripts/create-review.sh
```

**Input JSON:**
```json
{
  "pr_number": 123,
  "summary": "Overall review summary (optional)",
  "comments": [
    {
      "path": "src/app.ts",
      "line": 42,
      "body": "**Critical:** Missing null check\n\n**Why:** Can cause runtime error\n\n**Fix:** Add `if (value != null)`"
    }
  ]
}
```

**Output:**
```json
{
  "review_id": 456789,
  "url": "https://github.com/owner/repo/pull/123#pullrequestreview-456789",
  "comment_count": 1,
  "status": "PENDING"
}
```

### submit-review.sh

Submit a pending review with an event type.

```bash
${SKILL_DIR}/scripts/submit-review.sh <pr_number> <review_id> <event> [body]
```

**Events:**
- `APPROVE` - Approve the PR
- `REQUEST_CHANGES` - Request changes before merge
- `COMMENT` - Leave feedback without approval/rejection

**Example:**
```bash
${SKILL_DIR}/scripts/submit-review.sh 123 456789 REQUEST_CHANGES "Please address the inline comments"
```

## Comment Format

For code review comments, use this format for clarity:

```markdown
**[Severity]:** Brief description

**Why:** Explanation of the issue

**Fix:** Suggested solution or code example
```

Severity levels:
- **Critical** - Must fix before merge
- **Warning** - Should fix
- **Suggestion** - Consider for improvement

## Error Handling

Scripts return JSON errors:

```json
{
  "error": true,
  "message": "gh CLI not authenticated. Run 'gh auth login' first.",
  "code": "AUTH_REQUIRED"
}
```

Error codes:
- `AUTH_REQUIRED` - Run `gh auth login`
- `NO_PR` - No PR found for current branch
- `API_ERROR` - GitHub API error (check message)
- `INVALID_INPUT` - Invalid JSON input

## Workflow Example

1. **Get PR info:**
   ```bash
   PR_INFO=$(${SKILL_DIR}/scripts/pr-info.sh)
   ```

2. **Review the code** and collect findings

3. **Create pending review:**
   ```bash
   echo '{"pr_number":123,"comments":[...]}' | ${SKILL_DIR}/scripts/create-review.sh
   ```

4. **User reviews comments on GitHub** and edits if needed

5. **User submits review** via GitHub UI or:
   ```bash
   ${SKILL_DIR}/scripts/submit-review.sh 123 $REVIEW_ID COMMENT
   ```

## Requirements

- `gh` CLI installed and authenticated (`gh auth login`)
- `jq` for JSON processing
- Git repository with GitHub remote

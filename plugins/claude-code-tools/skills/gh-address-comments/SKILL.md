---
name: gh-address-comments
description: Address review/issue comments on the open GitHub PR for the current branch. Fetches all comments and review threads, summarizes what needs attention, and helps apply fixes. Use when responding to PR feedback, resolving review comments, or when user mentions "address comments" or "fix review feedback".
allowed-tools: Bash(gh:*), Bash(jq:*), Read, Write, Edit
---

# GitHub Address Comments

Fetch and address review comments on the open PR for the current branch using the `gh` CLI.

## Quick Start

```bash
# Fetch all comments for current branch's PR
${SKILL_DIR}/scripts/fetch-comments.sh

# Fetch comments for specific PR
${SKILL_DIR}/scripts/fetch-comments.sh 123

# Reply to a review thread after fixing
${SKILL_DIR}/scripts/reply-to-thread.sh "PRRT_threadId" "Fixed in this commit"
```

## Workflow

### Step 1: Fetch Comments

Run the fetch script to get all PR comments:

```bash
COMMENTS=$(${SKILL_DIR}/scripts/fetch-comments.sh)
```

### Step 2: Summarize and Number

Present a numbered list of actionable items:

1. Review each `review_threads` entry (inline comments on specific lines)
2. Review each `conversation_comments` entry (general PR comments)
3. Skip resolved threads (`isResolved: true`)
4. Summarize what fix is needed for each

**Example summary format:**

```
## PR Comments Needing Attention

1. [src/app.ts:42] Missing null check before accessing property
2. [src/utils.ts:15-20] Consider extracting to helper function
3. [General] Add tests for edge cases

Which comments would you like me to address? (e.g., "1,3" or "all")
```

### Step 3: User Selection

Ask which numbered comments to address. Options:
- Specific numbers: `1,3`
- All: `all`
- None: `none`

### Step 4: Apply Fixes

For each selected comment:
1. Read the relevant file
2. Apply the requested fix
3. Mark as addressed in summary

### Step 5: Reply to Addressed Comments

After applying fixes, reply to the review threads to acknowledge:

```bash
# For each addressed thread (use the thread id from fetch-comments.sh)
${SKILL_DIR}/scripts/reply-to-thread.sh "$THREAD_ID" "Fixed in this commit"
```

**Suggested reply formats:**

- `"Fixed in commit abc123"` - Reference the fix commit
- `"Addressed by [description of change]"` - Describe the fix
- `"Will address in follow-up PR"` - For deferred items

## Script Documentation

### fetch-comments.sh

Fetches all PR comments using GitHub GraphQL API.

**Usage:**

```bash
${SKILL_DIR}/scripts/fetch-comments.sh [PR_NUMBER]
```

**Output:**

```json
{
  "pull_request": {
    "number": 123,
    "url": "https://github.com/owner/repo/pull/123",
    "title": "Add new feature",
    "state": "OPEN",
    "owner": "owner",
    "repo": "repo"
  },
  "conversation_comments": [
    {
      "id": "IC_...",
      "body": "Please add tests",
      "author": "reviewer",
      "createdAt": "2024-01-15T10:00:00Z"
    }
  ],
  "reviews": [
    {
      "id": "PRR_...",
      "state": "CHANGES_REQUESTED",
      "body": "Good start, but needs some changes",
      "author": "reviewer",
      "submittedAt": "2024-01-15T10:00:00Z"
    }
  ],
  "review_threads": [
    {
      "id": "PRRT_...",
      "isResolved": false,
      "isOutdated": false,
      "path": "src/app.ts",
      "line": 42,
      "comments": [
        {
          "id": "PRRC_...",
          "body": "Missing null check here",
          "author": "reviewer",
          "createdAt": "2024-01-15T10:00:00Z"
        }
      ]
    }
  ]
}
```

### reply-to-thread.sh

Reply to a PR review thread after addressing feedback.

**Usage:**

```bash
${SKILL_DIR}/scripts/reply-to-thread.sh <thread_id> <body>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `thread_id` | The review thread ID from `fetch-comments.sh` (e.g., `PRRT_kwDO...`) |
| `body` | The reply message text |

**Output:**

```json
{
  "id": "PRRC_...",
  "body": "Fixed in commit abc123",
  "url": "https://github.com/owner/repo/pull/123#discussion_r12345",
  "author": "your-username",
  "createdAt": "2024-01-15T10:30:00Z"
}
```

**Example:**

```bash
# After fixing an issue, reply to acknowledge
${SKILL_DIR}/scripts/reply-to-thread.sh "PRRT_kwDOExample123" "Fixed by adding null check"
```

## Error Handling

The script returns JSON errors:

```json
{
  "error": true,
  "message": "gh CLI not authenticated. Run 'gh auth login' first.",
  "code": "AUTH_REQUIRED"
}
```

**Error codes:**

| Code | Description |
|------|-------------|
| `GH_NOT_INSTALLED` | gh CLI not installed |
| `AUTH_REQUIRED` | Run `gh auth login` |
| `JQ_NOT_INSTALLED` | jq not installed |
| `NOT_GIT_REPO` | Not in a git repository |
| `NO_PR` | No PR found for current branch |
| `API_ERROR` | GitHub API error |

## Guidelines

- Always fetch fresh comments before addressing (PRs update frequently)
- Skip resolved threads unless user explicitly asks
- Skip outdated threads (code has changed) unless relevant
- For inline comments, show the file path and line number
- Apply fixes one at a time, verifying each works
- If a comment is unclear, ask for clarification before fixing
- After fixing a comment, reply to the thread to acknowledge the fix
- Use descriptive replies that explain how the issue was resolved

## Requirements

- `gh` CLI installed and authenticated (`gh auth login`)
- `jq` for JSON processing
- Git repository with GitHub remote
- Open PR for current branch (or specify PR number)

## Related Skills

- [gh-pr-review](../gh-pr-review/SKILL.md) - Create reviews (outbound)
- This skill - Address reviews (inbound)

---

*Adapted from [openai/skills/gh-address-comments](https://github.com/openai/skills/tree/main/skills/.curated/gh-address-comments)*

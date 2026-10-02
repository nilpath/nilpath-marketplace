# GitHub PR Review API Reference

## Endpoints Used

### Create a Review

```
POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews
```

**Request body:**
```json
{
  "commit_id": "sha (optional, defaults to latest)",
  "body": "Review summary",
  "event": "APPROVE | REQUEST_CHANGES | COMMENT (omit for PENDING)",
  "comments": [
    {
      "path": "relative/path/to/file.ts",
      "line": 42,
      "body": "Comment text"
    }
  ]
}
```

**Key insight:** Omitting the `event` field creates a PENDING review that requires separate submission.

### Submit a Pending Review

```
POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}/events
```

**Request body:**
```json
{
  "event": "APPROVE | REQUEST_CHANGES | COMMENT",
  "body": "Optional final message"
}
```

## Comment Object Fields

| Field | Required | Description |
|-------|----------|-------------|
| `path` | Yes | Relative file path in the repository |
| `body` | Yes | The comment text (markdown supported) |
| `line` | Yes* | Line number in the NEW file (end line for multi-line) |
| `side` | Recommended | `RIGHT` (additions/context) or `LEFT` (deletions). **Default: RIGHT** |
| `start_line` | No | First line for multi-line comments (must be < `line`) |
| `start_side` | No | Side for start_line (defaults to match `side`) |

*Either `line` or `position` is required. We use `line` for simplicity.

### Line Positioning Rules

1. **Single-line on new/modified code**: `{path, line, body}` - side defaults to RIGHT
2. **Single-line on deleted code**: `{path, line, side: "LEFT", body}`
3. **Multi-line range**: `{path, start_line, line, body}` - covers start_line to line
4. **Multi-line across sides**: `{path, start_line, start_side: "LEFT", line, side: "RIGHT", body}`

### Example: Multi-line Comment

```json
{
  "path": "src/app.ts",
  "start_line": 15,
  "line": 20,
  "side": "RIGHT",
  "body": "Consider extracting this logic into a separate function"
}
```

## Review Events

| Event | Description |
|-------|-------------|
| `APPROVE` | Approve the changes |
| `REQUEST_CHANGES` | Block merge until changes addressed |
| `COMMENT` | Leave feedback without approval/rejection |
| *(omitted)* | Create PENDING review (not visible until submitted) |

## Response Fields

### Review Creation Response

```json
{
  "id": 456789,
  "node_id": "PRR_...",
  "user": { ... },
  "body": "Review summary",
  "state": "PENDING",
  "html_url": "https://github.com/...",
  "pull_request_url": "https://api.github.com/...",
  "submitted_at": null,
  "commit_id": "abc123..."
}
```

Note: `submitted_at` is `null` for PENDING reviews.

### Review Submission Response

```json
{
  "id": 456789,
  "state": "CHANGES_REQUESTED",
  "submitted_at": "2024-01-15T10:30:00Z",
  ...
}
```

## Error Responses

### Common Errors

**422 Unprocessable Entity - Path not in diff:**
```json
{
  "message": "Validation Failed",
  "errors": [
    {
      "resource": "PullRequestReviewComment",
      "field": "path",
      "code": "invalid"
    }
  ]
}
```

**404 Not Found:**
```json
{
  "message": "Not Found"
}
```

**401 Unauthorized:**
```json
{
  "message": "Bad credentials"
}
```

## Rate Limits

- Authenticated requests: 5,000/hour
- Review creation counts as 1 request + 1 per comment
- Check limits: `gh api rate_limit`

## References

- [REST API: Pull Request Reviews](https://docs.github.com/en/rest/pulls/reviews)
- [REST API: Review Comments](https://docs.github.com/en/rest/pulls/comments)
- [gh CLI](https://cli.github.com/manual/gh_api)

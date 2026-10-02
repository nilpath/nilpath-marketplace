#!/bin/bash
# reply-to-thread.sh - Reply to a PR review thread
# Usage: ./reply-to-thread.sh <thread_id> <body>
# Output: {"id":"...","body":"...","url":"...","author":"...","createdAt":"..."}

set -euo pipefail

error_json() {
    echo "{\"error\":true,\"message\":\"$1\",\"code\":\"$2\"}"
    exit 1
}

show_help() {
    cat << EOF
Usage: ./reply-to-thread.sh <thread_id> <body>

Arguments:
  thread_id   The review thread ID (PRRT_... from fetch-comments.sh)
  body        The reply message text

Examples:
  ./reply-to-thread.sh "PRRT_kwDOExample" "Fixed in commit abc123"
  ./reply-to-thread.sh "PRRT_kwDOExample" "Addressed by extracting to helper function"
EOF
    exit 0
}

# Check for help flag
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    show_help
fi

# Check dependencies
if ! command -v gh &> /dev/null; then
    error_json "gh CLI not installed. Install from https://cli.github.com/" "GH_NOT_INSTALLED"
fi

if ! gh auth status &> /dev/null; then
    error_json "gh CLI not authenticated. Run 'gh auth login' first." "AUTH_REQUIRED"
fi

if ! command -v jq &> /dev/null; then
    error_json "jq not installed. Install with: brew install jq (macOS) or apt install jq (Linux)" "JQ_NOT_INSTALLED"
fi

# Parse arguments
THREAD_ID="${1:-}"
BODY="${2:-}"

if [ -z "$THREAD_ID" ]; then
    error_json "thread_id is required" "INVALID_INPUT"
fi

if [ -z "$BODY" ]; then
    error_json "body is required" "INVALID_INPUT"
fi

# GraphQL mutation
MUTATION='
mutation AddReply($threadId: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: {
    pullRequestReviewThreadId: $threadId
    body: $body
  }) {
    comment {
      id
      body
      url
      createdAt
      author { login }
    }
  }
}
'

# Build variables
VARIABLES=$(jq -n \
    --arg threadId "$THREAD_ID" \
    --arg body "$BODY" \
    '{threadId: $threadId, body: $body}')

# Build payload
PAYLOAD=$(jq -n \
    --arg query "$MUTATION" \
    --argjson variables "$VARIABLES" \
    '{query: $query, variables: $variables}')

# Execute mutation
RESPONSE=$(gh api graphql --input - <<< "$PAYLOAD" 2>&1) || {
    error_json "GitHub API error: $RESPONSE" "API_ERROR"
}

# Check for GraphQL errors
if echo "$RESPONSE" | jq -e '.errors' > /dev/null 2>&1; then
    ERROR_MSG=$(echo "$RESPONSE" | jq -r '.errors[0].message // "Unknown GraphQL error"')
    error_json "$ERROR_MSG" "API_ERROR"
fi

# Extract result
COMMENT=$(echo "$RESPONSE" | jq '.data.addPullRequestReviewThreadReply.comment')

if [ "$COMMENT" = "null" ]; then
    error_json "Failed to add reply - no comment returned" "API_ERROR"
fi

# Output result
echo "$COMMENT" | jq '{
    id: .id,
    body: .body,
    url: .url,
    author: (.author.login // "unknown"),
    createdAt: .createdAt
}'

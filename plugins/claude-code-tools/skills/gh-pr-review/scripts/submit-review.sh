#!/bin/bash
# submit-review.sh - Submit a pending PR review
# Usage: ./submit-review.sh <pr_number> <review_id> <event> [body]
# Events: APPROVE, REQUEST_CHANGES, COMMENT

set -e

error_json() {
    echo "{\"error\":true,\"message\":\"$1\",\"code\":\"$2\"}"
    exit 1
}

show_help() {
    cat << EOF
Usage: ./submit-review.sh <pr_number> <review_id> <event> [body]

Arguments:
  pr_number   The PR number
  review_id   The review ID from create-review.sh
  event       One of: APPROVE, REQUEST_CHANGES, COMMENT
  body        Optional message to include with the review

Examples:
  ./submit-review.sh 123 456789 APPROVE
  ./submit-review.sh 123 456789 REQUEST_CHANGES "Please fix the issues"
  ./submit-review.sh 123 456789 COMMENT "Looks good overall"
EOF
    exit 0
}

# Check for help flag
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_help
fi

# Check dependencies
if ! command -v gh &> /dev/null; then
    error_json "gh CLI not installed" "GH_NOT_INSTALLED"
fi

if ! gh auth status &> /dev/null; then
    error_json "gh CLI not authenticated. Run 'gh auth login' first." "AUTH_REQUIRED"
fi

if ! command -v jq &> /dev/null; then
    error_json "jq not installed" "JQ_NOT_INSTALLED"
fi

# Parse arguments
PR_NUMBER="$1"
REVIEW_ID="$2"
EVENT="$3"
BODY="${4:-}"

# Validate arguments
if [ -z "$PR_NUMBER" ]; then
    error_json "pr_number is required" "INVALID_INPUT"
fi

if [ -z "$REVIEW_ID" ]; then
    error_json "review_id is required" "INVALID_INPUT"
fi

if [ -z "$EVENT" ]; then
    error_json "event is required (APPROVE, REQUEST_CHANGES, or COMMENT)" "INVALID_INPUT"
fi

# Validate event type
case "$EVENT" in
    APPROVE|REQUEST_CHANGES|COMMENT)
        ;;
    *)
        error_json "Invalid event type: $EVENT. Must be APPROVE, REQUEST_CHANGES, or COMMENT" "INVALID_INPUT"
        ;;
esac

# Get repo info
REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null) || {
    error_json "Could not determine repository" "REPO_ERROR"
}

# Get PR base URL (works for GitHub Enterprise)
PR_URL=$(gh pr view "$PR_NUMBER" --json url -q '.url' 2>/dev/null) || {
    # Fallback: construct URL (may be incorrect for GitHub Enterprise)
    echo "Warning: Could not fetch PR URL, constructing github.com URL as fallback" >&2
    PR_URL="https://github.com/$REPO/pull/$PR_NUMBER"
}

# Build API request body
if [ -n "$BODY" ]; then
    API_BODY=$(jq -n --arg event "$EVENT" --arg body "$BODY" '{event: $event, body: $body}')
else
    API_BODY=$(jq -n --arg event "$EVENT" '{event: $event}')
fi

# Submit the review via GitHub API
RESPONSE=$(echo "$API_BODY" | gh api "repos/$REPO/pulls/$PR_NUMBER/reviews/$REVIEW_ID/events" \
    --method POST \
    --input - \
    2>&1) || {
    error_json "GitHub API error: $RESPONSE" "API_ERROR"
}

# Parse response
SUBMITTED_AT=$(echo "$RESPONSE" | jq -r '.submitted_at // empty')
if [ -z "$SUBMITTED_AT" ]; then
    ERROR_MSG=$(echo "$RESPONSE" | jq -r '.message // "Unknown error"')
    error_json "Failed to submit review: $ERROR_MSG" "API_ERROR"
fi

# Build output
jq -n \
    --arg url "$PR_URL#pullrequestreview-$REVIEW_ID" \
    --arg event "$EVENT" \
    --arg submitted_at "$SUBMITTED_AT" \
    '{
        submitted: true,
        url: $url,
        event: $event,
        submitted_at: $submitted_at
    }'

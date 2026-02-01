#!/bin/bash
# create-review.sh - Create a pending PR review with line comments
# Usage: echo '$JSON' | ./create-review.sh
# Input: {"pr_number":123,"summary":"...","comments":[{"path":"file.ts","line":42,"body":"..."}]}
# Output: {"review_id":N,"url":"...","comment_count":N,"status":"PENDING"}

set -e

error_json() {
    echo "{\"error\":true,\"message\":\"$1\",\"code\":\"$2\"}"
    exit 1
}

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

# Read JSON from stdin
INPUT=$(cat)

# Validate input
if [ -z "$INPUT" ]; then
    error_json "No input provided. Pipe JSON to stdin." "INVALID_INPUT"
fi

# Parse input
PR_NUMBER=$(echo "$INPUT" | jq -r '.pr_number // empty')
SUMMARY=$(echo "$INPUT" | jq -r '.summary // ""')
COMMENTS=$(echo "$INPUT" | jq -c '.comments // []')

if [ -z "$PR_NUMBER" ]; then
    error_json "pr_number is required" "INVALID_INPUT"
fi

# Validate comments array
COMMENT_COUNT=$(echo "$COMMENTS" | jq 'length')
if [ "$COMMENT_COUNT" -eq 0 ]; then
    error_json "At least one comment is required" "INVALID_INPUT"
fi

# Get repo info
REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null) || {
    error_json "Could not determine repository" "REPO_ERROR"
}

# Get files in the PR diff to validate comment paths
DIFF_FILES=$(gh pr diff "$PR_NUMBER" --name-only 2>/dev/null) || {
    error_json "Could not get PR diff for #$PR_NUMBER" "DIFF_ERROR"
}

# Filter comments to only include files in the diff
VALID_COMMENTS=$(echo "$COMMENTS" | jq -c --arg diff_files "$DIFF_FILES" '
    ($diff_files | split("\n") | map(select(length > 0))) as $files |
    map(select(.path as $p | $files | any(. == $p)))
')

VALID_COUNT=$(echo "$VALID_COMMENTS" | jq 'length')
SKIPPED_COUNT=$((COMMENT_COUNT - VALID_COUNT))

# Log skipped paths to stderr
if [ "$SKIPPED_COUNT" -gt 0 ]; then
    SKIPPED_PATHS=$(echo "$COMMENTS" | jq -r --argjson valid "$VALID_COMMENTS" '
        [.[].path] - [$valid[].path] | unique | .[]
    ')
    echo "Warning: Skipped $SKIPPED_COUNT comment(s) for files not in PR diff:" >&2
    echo "$SKIPPED_PATHS" | while read -r path; do
        echo "  - $path" >&2
    done
fi

if [ "$VALID_COUNT" -eq 0 ]; then
    error_json "None of the comment paths are in the PR diff" "NO_VALID_COMMENTS"
fi

# Build the API request body
# Note: We intentionally omit the "event" field to create a PENDING review
API_BODY=$(jq -n \
    --arg body "$SUMMARY" \
    --argjson comments "$VALID_COMMENTS" \
    '{body: $body, comments: $comments}')

# Create the review via GitHub API
RESPONSE=$(echo "$API_BODY" | gh api "repos/$REPO/pulls/$PR_NUMBER/reviews" \
    --method POST \
    --input - \
    2>&1) || {
    error_json "GitHub API error: $RESPONSE" "API_ERROR"
}

# Parse response
REVIEW_ID=$(echo "$RESPONSE" | jq -r '.id // empty')
if [ -z "$REVIEW_ID" ]; then
    ERROR_MSG=$(echo "$RESPONSE" | jq -r '.message // "Unknown error"')
    error_json "Failed to create review: $ERROR_MSG" "API_ERROR"
fi

# Build output
jq -n \
    --argjson review_id "$REVIEW_ID" \
    --arg url "https://github.com/$REPO/pull/$PR_NUMBER#pullrequestreview-$REVIEW_ID" \
    --argjson comment_count "$VALID_COUNT" \
    --argjson skipped_count "$SKIPPED_COUNT" \
    '{
        review_id: $review_id,
        url: $url,
        comment_count: $comment_count,
        skipped_count: $skipped_count,
        status: "PENDING"
    }'

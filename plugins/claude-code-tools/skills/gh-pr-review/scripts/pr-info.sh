#!/bin/bash
# pr-info.sh - Get PR context information
# Usage: ./pr-info.sh [PR_NUMBER]
# Output: JSON with pr_number, repo, url, files

set -e

# Colors for stderr messages
RED='\033[0;31m'
NC='\033[0m' # No Color

error_json() {
    echo "{\"error\":true,\"message\":\"$1\",\"code\":\"$2\"}"
    exit 1
}

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    error_json "gh CLI not installed. Install from https://cli.github.com/" "GH_NOT_INSTALLED"
fi

# Check if gh is authenticated
if ! gh auth status &> /dev/null; then
    error_json "gh CLI not authenticated. Run 'gh auth login' first." "AUTH_REQUIRED"
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    error_json "jq not installed. Install with: brew install jq (macOS) or apt install jq (Linux)" "JQ_NOT_INSTALLED"
fi

# Check if we're in a git repo
if ! git rev-parse --is-inside-work-tree &> /dev/null; then
    error_json "Not in a git repository" "NOT_GIT_REPO"
fi

PR_NUMBER="$1"

# If no PR number provided, try to detect from current branch
if [ -z "$PR_NUMBER" ]; then
    PR_NUMBER=$(gh pr view --json number -q '.number' 2>/dev/null || echo "")

    if [ -z "$PR_NUMBER" ]; then
        error_json "No PR found for current branch. Provide a PR number or create a PR first." "NO_PR"
    fi
fi

# Get PR details
PR_DATA=$(gh pr view "$PR_NUMBER" --json number,url,headRepository 2>/dev/null) || {
    error_json "PR #$PR_NUMBER not found" "PR_NOT_FOUND"
}

# Get repo in owner/repo format
REPO=$(echo "$PR_DATA" | jq -r '.headRepository.owner.login + "/" + .headRepository.name')

# If headRepository is null, try to get from current repo
if [[ "$REPO" =~ ^(null/null|/)$ ]] || [ -z "$REPO" ]; then
    REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null) || {
        error_json "Could not determine repository" "REPO_ERROR"
    }
fi

# Get URL
URL=$(echo "$PR_DATA" | jq -r '.url')

# Get changed files
FILES=$(gh pr diff "$PR_NUMBER" --name-only 2>/dev/null | jq -R -s 'split("\n") | map(select(length > 0))') || {
    error_json "Could not get PR diff" "DIFF_ERROR"
}

# Output JSON
jq -n \
    --argjson pr_number "$PR_NUMBER" \
    --arg repo "$REPO" \
    --arg url "$URL" \
    --argjson files "$FILES" \
    '{pr_number: $pr_number, repo: $repo, url: $url, files: $files}'

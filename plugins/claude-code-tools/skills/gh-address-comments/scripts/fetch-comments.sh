#!/bin/bash
# fetch-comments.sh - Fetch PR comments for current branch
# Usage: ./fetch-comments.sh [PR_NUMBER]
# Output: JSON with pull_request, conversation_comments, reviews, review_threads
#
# Adapted from: https://github.com/openai/skills/tree/main/skills/.curated/gh-address-comments

set -e

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

# Get owner and repo from PR
PR_DATA=$(gh pr view "$PR_NUMBER" --json number,url,title,state,headRepository 2>/dev/null) || {
    error_json "PR #$PR_NUMBER not found" "PR_NOT_FOUND"
}

OWNER=$(echo "$PR_DATA" | jq -r '.headRepository.owner.login // empty')
REPO=$(echo "$PR_DATA" | jq -r '.headRepository.name // empty')
TITLE=$(echo "$PR_DATA" | jq -r '.title')
STATE=$(echo "$PR_DATA" | jq -r '.state')
URL=$(echo "$PR_DATA" | jq -r '.url')

# Fallback for owner/repo if headRepository is null
if [ -z "$OWNER" ] || [ -z "$REPO" ]; then
    REPO_INFO=$(gh repo view --json owner,name 2>/dev/null) || {
        error_json "Could not determine repository" "REPO_ERROR"
    }
    OWNER=$(echo "$REPO_INFO" | jq -r '.owner.login')
    REPO=$(echo "$REPO_INFO" | jq -r '.name')
fi

# GraphQL query for fetching PR comments
QUERY='
query($owner: String!, $repo: String!, $number: Int!, $commentsCursor: String, $reviewsCursor: String, $threadsCursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      comments(first: 100, after: $commentsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          body
          createdAt
          updatedAt
          author { login }
        }
      }
      reviews(first: 100, after: $reviewsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          state
          body
          submittedAt
          author { login }
        }
      }
      reviewThreads(first: 100, after: $threadsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          diffSide
          startLine
          startDiffSide
          originalLine
          originalStartLine
          resolvedBy { login }
          comments(first: 100) {
            nodes {
              id
              body
              createdAt
              updatedAt
              author { login }
            }
          }
        }
      }
    }
  }
}
'

# Initialize arrays for aggregating results
ALL_COMMENTS="[]"
ALL_REVIEWS="[]"
ALL_THREADS="[]"

# Pagination cursors
COMMENTS_CURSOR=""
REVIEWS_CURSOR=""
THREADS_CURSOR=""

# Fetch with pagination
while true; do
    # Build variables JSON
    VARIABLES=$(jq -n \
        --arg owner "$OWNER" \
        --arg repo "$REPO" \
        --argjson number "$PR_NUMBER" \
        --arg commentsCursor "$COMMENTS_CURSOR" \
        --arg reviewsCursor "$REVIEWS_CURSOR" \
        --arg threadsCursor "$THREADS_CURSOR" \
        '{
            owner: $owner,
            repo: $repo,
            number: $number
        } + (if $commentsCursor != "" then {commentsCursor: $commentsCursor} else {} end)
          + (if $reviewsCursor != "" then {reviewsCursor: $reviewsCursor} else {} end)
          + (if $threadsCursor != "" then {threadsCursor: $threadsCursor} else {} end)')

    # Build complete GraphQL request payload
    PAYLOAD=$(jq -n \
        --arg query "$QUERY" \
        --argjson variables "$VARIABLES" \
        '{query: $query, variables: $variables}')

    # Execute GraphQL query
    RESPONSE=$(gh api graphql --input - <<< "$PAYLOAD" 2>&1) || {
        error_json "GitHub API error: $RESPONSE" "API_ERROR"
    }

    # Check for GraphQL errors
    if echo "$RESPONSE" | jq -e '.errors' > /dev/null 2>&1; then
        ERROR_MSG=$(echo "$RESPONSE" | jq -r '.errors[0].message // "Unknown GraphQL error"')
        error_json "$ERROR_MSG" "API_ERROR"
    fi

    PR_RESPONSE=$(echo "$RESPONSE" | jq '.data.repository.pullRequest')

    # Check if PR response is null (PR not found or not accessible)
    if [ "$PR_RESPONSE" = "null" ]; then
        error_json "PR #$PR_NUMBER not found or not accessible" "PR_NOT_FOUND"
    fi

    # Aggregate comments
    NEW_COMMENTS=$(echo "$PR_RESPONSE" | jq '[.comments.nodes[] | {
        id: .id,
        body: .body,
        author: (.author.login // "unknown"),
        createdAt: .createdAt,
        updatedAt: .updatedAt
    }]')
    ALL_COMMENTS=$(echo "$ALL_COMMENTS $NEW_COMMENTS" | jq -s 'add')

    # Aggregate reviews
    NEW_REVIEWS=$(echo "$PR_RESPONSE" | jq '[.reviews.nodes[] | select(.body != null and .body != "") | {
        id: .id,
        state: .state,
        body: .body,
        author: (.author.login // "unknown"),
        submittedAt: .submittedAt
    }]')
    ALL_REVIEWS=$(echo "$ALL_REVIEWS $NEW_REVIEWS" | jq -s 'add')

    # Aggregate review threads
    NEW_THREADS=$(echo "$PR_RESPONSE" | jq '[.reviewThreads.nodes[] | {
        id: .id,
        isResolved: .isResolved,
        isOutdated: .isOutdated,
        path: .path,
        line: .line,
        startLine: .startLine,
        diffSide: .diffSide,
        resolvedBy: (.resolvedBy.login // null),
        comments: [.comments.nodes[] | {
            id: .id,
            body: .body,
            author: (.author.login // "unknown"),
            createdAt: .createdAt,
            updatedAt: .updatedAt
        }]
    }]')
    ALL_THREADS=$(echo "$ALL_THREADS $NEW_THREADS" | jq -s 'add')

    # Check pagination
    COMMENTS_HAS_NEXT=$(echo "$PR_RESPONSE" | jq -r '.comments.pageInfo.hasNextPage')
    REVIEWS_HAS_NEXT=$(echo "$PR_RESPONSE" | jq -r '.reviews.pageInfo.hasNextPage')
    THREADS_HAS_NEXT=$(echo "$PR_RESPONSE" | jq -r '.reviewThreads.pageInfo.hasNextPage')

    # Update cursors if there are more pages
    if [ "$COMMENTS_HAS_NEXT" = "true" ]; then
        COMMENTS_CURSOR=$(echo "$PR_RESPONSE" | jq -r '.comments.pageInfo.endCursor')
    else
        COMMENTS_CURSOR=""
    fi

    if [ "$REVIEWS_HAS_NEXT" = "true" ]; then
        REVIEWS_CURSOR=$(echo "$PR_RESPONSE" | jq -r '.reviews.pageInfo.endCursor')
    else
        REVIEWS_CURSOR=""
    fi

    if [ "$THREADS_HAS_NEXT" = "true" ]; then
        THREADS_CURSOR=$(echo "$PR_RESPONSE" | jq -r '.reviewThreads.pageInfo.endCursor')
    else
        THREADS_CURSOR=""
    fi

    # Break if no more pages
    if [ -z "$COMMENTS_CURSOR" ] && [ -z "$REVIEWS_CURSOR" ] && [ -z "$THREADS_CURSOR" ]; then
        break
    fi
done

# Output final JSON
jq -n \
    --argjson pr_number "$PR_NUMBER" \
    --arg url "$URL" \
    --arg title "$TITLE" \
    --arg state "$STATE" \
    --arg owner "$OWNER" \
    --arg repo "$REPO" \
    --argjson conversation_comments "$ALL_COMMENTS" \
    --argjson reviews "$ALL_REVIEWS" \
    --argjson review_threads "$ALL_THREADS" \
    '{
        pull_request: {
            number: $pr_number,
            url: $url,
            title: $title,
            state: $state,
            owner: $owner,
            repo: $repo
        },
        conversation_comments: $conversation_comments,
        reviews: $reviews,
        review_threads: $review_threads
    }'

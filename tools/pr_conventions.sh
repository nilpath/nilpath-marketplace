#!/usr/bin/env sh
set -eu

TYPES='feat|fix|perf|refactor|revert|docs|deps|chore|ci|test|style|build'

usage() {
  printf 'usage: %s --title <pr title>\n' "$0" >&2
  printf '       or set PR_NUMBER and optionally GH_REPO to fetch the title with gh\n' >&2
  exit 2
}

case "$#" in
  0)
    case "${PR_NUMBER:-}" in
      ''|0|*[!0-9]*)
        printf 'ERROR: PR_NUMBER must be a positive integer when --title is omitted.\n' >&2
        exit 2
        ;;
    esac
    GH_REPO="${GH_REPO:-${GITHUB_REPOSITORY:-nilpath/nilpath-marketplace}}"
    TITLE=$(GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}" gh api --hostname github.com \
      "repos/$GH_REPO/pulls/$PR_NUMBER" --jq '.title')
    ;;
  2)
    [ "$1" = "--title" ] || usage
    TITLE="$2"
    ;;
  *) usage ;;
esac

if [ "$(printf '%s\n' "$TITLE" | wc -l)" -eq 1 ] &&
  printf '%s\n' "$TITLE" | LC_ALL=C grep -qE "^($TYPES)(\([^()[:space:][:cntrl:]]+\))?!?: [^[:space:][:cntrl:]][^[:cntrl:]]*$"; then
  printf 'OK: title is a Conventional Commit\n'
  exit 0
fi

printf 'ERROR: PR title is not a Conventional Commit.\n' >&2
printf '  got: %s\n' "$TITLE" >&2
printf '  expected: <type>[optional scope][optional !]: <summary>\n' >&2
printf '  example: feat(nstack): add a verification skill\n' >&2
printf '  types: %s\n' "$(printf '%s' "$TYPES" | tr '|' ' ')" >&2
printf 'Retitle the PR so its squash commit has a clear type for release planning.\n' >&2
exit 1

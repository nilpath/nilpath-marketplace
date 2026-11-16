#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  printf 'usage: %s <base-commit>\n' "$0" >&2
  exit 2
fi

git diff --exit-code --name-only --no-renames "$1...HEAD" -- \
  dist .claude-plugin/marketplace.json \
  .agents/plugins/marketplace.json .github/plugin/marketplace.json

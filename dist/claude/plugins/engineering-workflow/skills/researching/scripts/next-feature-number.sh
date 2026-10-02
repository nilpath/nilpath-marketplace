#!/usr/bin/env bash
# Outputs the next sequential 3-digit feature number based on docs/features/.
# Usage: bash ${CLAUDE_SKILL_DIR}/scripts/next-feature-number.sh
# Example output: 003
max=0
if [ -d docs/features ]; then
  for dir in docs/features/*/; do
    [ -d "$dir" ] || continue
    num=$(basename "$dir" | grep -oE '^[0-9]+')
    [ -n "$num" ] && [ "$((10#$num))" -gt "$max" ] && max=$((10#$num))
  done
fi
printf '%03d\n' $((max + 1))

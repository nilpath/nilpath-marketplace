#!/bin/bash
# validate-mermaid.sh - Validate Mermaid diagram syntax
#
# Usage:
#   ./validate-mermaid.sh <file.md or file.mmd>
#   ./validate-mermaid.sh -              # Read from stdin
#   echo 'flowchart LR\n  A-->B' | ./validate-mermaid.sh -
#
# Output (JSON):
#   Success: {"valid":true,"message":"Diagram syntax is valid"}
#   Error:   {"error":true,"message":"...","code":"ERROR_CODE"}
#
# Error codes:
#   NPX_NOT_FOUND     - npx (Node.js) not installed
#   INVALID_INPUT     - No input file provided
#   FILE_NOT_FOUND    - Input file does not exist
#   NO_MERMAID_BLOCK  - No mermaid code block found in .md file
#   SYNTAX_ERROR      - Mermaid syntax validation failed

set -e

# JSON output helpers
error_json() {
    local message="$1"
    local code="$2"
    # Escape quotes in message
    message="${message//\"/\\\"}"
    echo "{\"error\":true,\"message\":\"$message\",\"code\":\"$code\"}"
    exit 1
}

success_json() {
    echo '{"valid":true,"message":"Diagram syntax is valid"}'
    exit 0
}

# Check for npx
if ! command -v npx &> /dev/null; then
    error_json "npx not found. Install Node.js to use validation." "NPX_NOT_FOUND"
fi

# Check input argument
INPUT_FILE="$1"

if [ -z "$INPUT_FILE" ]; then
    error_json "Usage: validate-mermaid.sh <file.md|file.mmd|->" "INVALID_INPUT"
fi

# Create temp files
TEMP_OUTPUT=$(mktemp /tmp/mermaid-out-XXXXXX.svg)
TEMP_INPUT=""
TEMP_MMD=""

cleanup() {
    rm -f "$TEMP_OUTPUT" "$TEMP_INPUT" "$TEMP_MMD" 2>/dev/null
}
trap cleanup EXIT

# Handle stdin
if [ "$INPUT_FILE" = "-" ]; then
    TEMP_INPUT=$(mktemp /tmp/mermaid-in-XXXXXX.mmd)
    cat > "$TEMP_INPUT"
    INPUT_FILE="$TEMP_INPUT"
fi

# Check file exists
if [ ! -f "$INPUT_FILE" ]; then
    error_json "File not found: $INPUT_FILE" "FILE_NOT_FOUND"
fi

# Extract mermaid code block from markdown if needed
if [[ "$INPUT_FILE" == *.md ]]; then
    TEMP_MMD=$(mktemp /tmp/mermaid-extract-XXXXXX.mmd)
    # Extract content between ```mermaid and ```
    awk '/^```mermaid$/,/^```$/{if(!/^```/) print}' "$INPUT_FILE" > "$TEMP_MMD"

    if [ ! -s "$TEMP_MMD" ]; then
        error_json "No mermaid code block found in file" "NO_MERMAID_BLOCK"
    fi
    INPUT_FILE="$TEMP_MMD"
fi

# Run mermaid-cli validation
OUTPUT=$(npx -y @mermaid-js/mermaid-cli -i "$INPUT_FILE" -o "$TEMP_OUTPUT" 2>&1) || {
    # Extract meaningful error message
    ERROR_MSG=$(echo "$OUTPUT" | grep -iE "(error|parse|syntax)" | head -1)
    if [ -z "$ERROR_MSG" ]; then
        ERROR_MSG="$OUTPUT"
    fi
    # Truncate long messages
    if [ ${#ERROR_MSG} -gt 200 ]; then
        ERROR_MSG="${ERROR_MSG:0:200}..."
    fi
    error_json "Syntax error: $ERROR_MSG" "SYNTAX_ERROR"
}

success_json

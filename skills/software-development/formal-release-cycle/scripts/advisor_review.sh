#!/bin/bash
# Spawn a technical-advisor review session using Claude Sonnet.
# Usage: bash advisor_review.sh "review prompt..." [--output /tmp/out.txt]
#
# WARNING: Use ABSOLUTE paths (~ tilde resolves to profile home, not real home).
# In Hermes terminal, use: bash /Users/greg/.hermes/profiles/johnny/scripts/advisor_review.sh

PROMPT="$1"
OUTPUT_FILE=""
if [ "$2" = "--output" ] || [ "$2" = "-o" ]; then
    OUTPUT_FILE="$3"
fi

if [ -n "$OUTPUT_FILE" ]; then
    hermes --profile technical-advisor chat -q "$PROMPT" \
        --toolsets file,terminal,web --quiet 2>&1 | tee "$OUTPUT_FILE"
else
    hermes --profile technical-advisor chat -q "$PROMPT" \
        --toolsets file,terminal,web --quiet 2>&1
fi

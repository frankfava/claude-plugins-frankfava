#!/bin/bash
# Report or set this session's voice mode. Resolves the live session id itself,
# because one captured earlier does not survive a branch or a resume.
set -u
DIR="$HOME/.claude"

session_id() {
  find "$DIR/projects" -name '*.jsonl' -maxdepth 2 -mmin -120 2>/dev/null \
    | xargs -r ls -t 2>/dev/null | head -1 | xargs -r basename | sed 's/\.jsonl$//'
}

SID=$(session_id)
FILE="$DIR/.talk-to-claude-mode.$SID"
WANT="${1:-}"

case "$WANT" in
  "")                              bash "$(dirname "$0")/../lib/mode.sh" "$SID" ;;
  off)                             rm -f "$FILE"; echo off ;;
  narrate|listen|converse)         echo "$WANT" > "$FILE"; echo "$WANT" ;;
  *) echo "usage: voice-mode.sh [off|narrate|listen|converse]" >&2; exit 2 ;;
esac

#!/bin/bash
# Hands-free on/off. Resolves the live session id, so a branched or resumed
# session cannot end up toggling a stale one.
set -u
DIR="$HOME/.claude"

session_id() {
  find "$DIR/projects" -name '*.jsonl' -maxdepth 2 -mmin -120 2>/dev/null \
    | xargs -r ls -t 2>/dev/null | head -1 | xargs -r basename | sed 's/\.jsonl$//'
}

SID=$(session_id)
FLAG="$DIR/.talk-to-claude-handsfree.$SID"

case "${1:-toggle}" in
  on)     : > "$FLAG"; echo "on" ;;
  off)    rm -f "$FLAG"; echo "off" ;;
  status) [[ -f "$FLAG" ]] && echo "on" || echo "off" ;;
  toggle) if [[ -f "$FLAG" ]]; then rm -f "$FLAG"; echo "off"; else : > "$FLAG"; echo "on"; fi ;;
  *)      echo "usage: voice-handsfree.sh on|off|toggle|status" >&2; exit 2 ;;
esac

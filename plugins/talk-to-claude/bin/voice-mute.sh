#!/bin/bash
# Mute control. Resolves the live session id itself, because a session that has
# been branched or resumed gets a new id and any value captured earlier is stale.
#
#   voice-mute.sh status
#   voice-mute.sh on [seconds]      this session
#   voice-mute.sh off
#   voice-mute.sh global-on [seconds]
#   voice-mute.sh global-off
#   voice-mute.sh here              speak here while muted everywhere

set -u
DIR="$HOME/.claude"
GLOBAL="$DIR/.talk-to-claude-muted"

# The live session is the transcript being written to right now. Anything else,
# including a value injected at session start, can be out of date.
session_id() {
  local newest
  newest=$(find "$DIR/projects" -name '*.jsonl' -maxdepth 2 -mmin -120 2>/dev/null \
    | xargs -r ls -t 2>/dev/null | head -1)
  [[ -n "$newest" ]] && basename "$newest" .jsonl
}

expiry() { [[ -n "${1:-}" ]] && echo $(( $(date +%s) + $1 )); }

SID=$(session_id)
CMD="${1:-status}"
SECS="${2:-}"

case "$CMD" in
  status)
    printf 'session: %s\n' "${SID:-unknown}"
    for f in "$GLOBAL" "$GLOBAL.$SID"; do
      [[ -f "$f" ]] && printf 'set: %s %s\n' "$(basename "$f")" "$(cat "$f" 2>/dev/null)"
    done
    [[ -f "$DIR/.talk-to-claude-unmuted.$SID" ]] && printf 'override: speaking here\n'
    bash "$(dirname "$0")/../lib/mute.sh" "$SID" \
      && printf 'result: silent\n' || printf 'result: speaks\n'
    ;;
  on)          expiry "$SECS" > "$GLOBAL.$SID"; echo "muted this session (${SECS:-indefinite})" ;;
  off)         rm -f "$GLOBAL.$SID" "$DIR/.talk-to-claude-unmuted.$SID"; echo "unmuted this session" ;;
  global-on)   expiry "$SECS" > "$GLOBAL"; echo "muted everywhere (${SECS:-indefinite})" ;;
  global-off)  rm -f "$GLOBAL"; echo "unmuted everywhere" ;;
  here)        : > "$DIR/.talk-to-claude-unmuted.$SID"; echo "speaking here despite global mute" ;;
  *)           echo "usage: voice-mute.sh status|on|off|global-on|global-off|here [seconds]" >&2; exit 2 ;;
esac

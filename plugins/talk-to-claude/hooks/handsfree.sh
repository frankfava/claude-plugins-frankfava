#!/bin/bash
# Stop hook: while hands-free is on, listen for a reply and hand it back so the
# turn continues. This is what makes the loop survive Claude going off to do
# work: the harness fires it when the turn ends, whatever happened before.
input=$(cat)

sid=$(jq -r '.session_id // ""' <<<"$input")
mode=$(bash "$(dirname "$0")/../lib/mode.sh" "$sid")
[[ "$mode" == listen || "$mode" == converse ]] || exit 0

# Blocking a Stop fires Stop again, flagged as re-entrant. Refusing on that flag
# is the usual guard against a hook that never lets go, and it also limits the
# conversation to exactly one exchange. Count instead: a real conversation is
# allowed to continue, a runaway one still terminates.
turns="$HOME/.claude/.talk-to-claude-turns.$sid"
count=$(cat "$turns" 2>/dev/null || echo 0)
if (( count >= ${VOICE_MAX_TURNS:-40} )); then
  rm -f "$turns"
  exit 0
fi

bash "$(dirname "$0")/../bin/voice-server.sh" 2>/dev/null

heard=$(curl -sS --max-time 300 -X POST "http://127.0.0.1:${VOICE_PORT:-51100}/listen" 2>/dev/null)
if [[ -z "${heard// /}" ]]; then
  rm -f "$turns"        # nothing said: let the turn end and reset the count
  exit 0
fi

echo $(( count + 1 )) > "$turns"
jq -n --arg h "$heard" '{decision:"block", reason:$h}'
exit 0

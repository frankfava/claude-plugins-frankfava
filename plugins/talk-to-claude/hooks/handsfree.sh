#!/bin/bash
# Stop hook: while hands-free is on, listen for a reply and hand it back so the
# turn continues. This is what makes the loop survive Claude going off to do
# work: the harness fires it when the turn ends, whatever happened before.
input=$(cat)

# A Stop hook that continues a turn re-fires. Without this it never lets go.
[[ "$(jq -r '.stop_hook_active // false' <<<"$input")" == "true" ]] && exit 0

sid=$(jq -r '.session_id // ""' <<<"$input")
[[ -n "$sid" && -f "$HOME/.claude/.talk-to-claude-handsfree.$sid" ]] || exit 0

bash "$(dirname "$0")/../bin/voice-server.sh" 2>/dev/null

# Wait for the answer to finish playing before opening the microphone, or it
# transcribes the computer and Claude replies to itself.
while [[ -f "${TMPDIR:-/tmp}/talk-to-claude-speaking" ]]; do sleep 0.2; done

heard=$(curl -sS --max-time 180 -X POST "http://127.0.0.1:${VOICE_PORT:-51100}/listen" 2>/dev/null)
[[ -z "${heard// /}" ]] && exit 0        # nothing said: let the turn end

jq -n --arg h "$heard" '{decision:"block", reason:$h}'
exit 0

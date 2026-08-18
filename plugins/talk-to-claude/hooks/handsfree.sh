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

# No wait for the speaker here. Listening starts immediately so you can talk
# over the answer, and the recorder stops it when it hears you. On laptop
# speakers set VOICE_BARGE=0, or every reply interrupts itself.

heard=$(curl -sS --max-time 180 -X POST "http://127.0.0.1:${VOICE_PORT:-51100}/listen" 2>/dev/null)
[[ -z "${heard// /}" ]] && exit 0        # nothing said: let the turn end

jq -n --arg h "$heard" '{decision:"block", reason:$h}'
exit 0

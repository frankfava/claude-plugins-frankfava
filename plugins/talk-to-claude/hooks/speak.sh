#!/bin/bash
# Stop hook: read Claude's final message aloud.
# Reads hook JSON on stdin. Writes nothing to stdout.

input=$(cat)

# Re-entrant Stop events would stack overlapping speech.
if [[ "$(jq -r '.stop_hook_active // false' <<<"$input")" == "true" ]]; then
  exit 0
fi

sid=$(jq -r '.session_id // ""' <<<"$input")
bash "$(dirname "$0")/../lib/mute.sh" "$sid" && exit 0

# Media apps hold a "Playing audio" power assertion while they play. Kokoro and
# `say` do not, so this never sees itself.
if pmset -g assertions 2>/dev/null | grep -q 'named: "Playing audio"'; then
  exit 0
fi

text=$(jq -r '.last_assistant_message // ""' <<<"$input")
[[ -z "$text" ]] && exit 0

# The server owns stripping, voice selection and interrupting the previous
# utterance. A POST costs a socket; speaking MCP from here cost 3.7 seconds.
bash "$(dirname "$0")/../bin/voice-server.sh" 2>/dev/null
printf '%s' "$text" \
  | curl -sS --max-time 5 -X POST --data-binary @- \
      "http://127.0.0.1:${VOICE_PORT:-51100}/say" >/dev/null 2>&1

exit 0

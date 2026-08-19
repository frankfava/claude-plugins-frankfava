#!/bin/bash
# SubagentStop hook: speak the fact of a subagent finishing, not its text.
# Subagent output is written for the main thread, not for a listener.

input=$(cat)

sid=$(jq -r '.session_id // ""' <<<"$input")
mode=$(bash "$(dirname "$0")/../lib/mode.sh" "$sid")
[[ "$mode" == narrate || "$mode" == converse ]] || exit 0

# SubagentStop also fires with an empty agent_type, which the matcher does not
# filter. An unnamed agent has nothing worth announcing, so say nothing.
type=$(jq -r '.agent_type // ""' <<<"$input")
[[ -z "$type" ]] && exit 0

# The answer outranks the marker. If speech is already playing, skip this one
# rather than cutting a sentence in half to announce an agent.
[[ -f "${TMPDIR:-/tmp}/talk-to-claude-speaking" ]] && exit 0

# Through the warm server so narration and the loop share a voice.
bash "$(dirname "$0")/../bin/voice-server.sh" 2>/dev/null
printf '%s' "$type finished" \
  | curl -sS --max-time 5 -X POST --data-binary @- \
      "http://127.0.0.1:${VOICE_PORT:-51100}/say" >/dev/null 2>&1
exit 0

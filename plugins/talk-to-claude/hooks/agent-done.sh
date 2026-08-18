#!/bin/bash
# SubagentStop hook: speak the fact of a subagent finishing, not its text.
# Subagent output is written for the main thread, not for a listener.

input=$(cat)

sid=$(jq -r '.session_id // ""' <<<"$input")
bash "$(dirname "$0")/../lib/mute.sh" "$sid" && exit 0

# Stay quiet while another app is playing. See speak.sh.
if pmset -g assertions 2>/dev/null | grep -q 'named: "Playing audio"'; then
  exit 0
fi

# SubagentStop also fires with an empty agent_type, which the matcher does not
# filter. An unnamed agent has nothing worth announcing, so say nothing.
type=$(jq -r '.agent_type // ""' <<<"$input")
[[ -z "$type" ]] && exit 0

# The answer outranks the marker. If speech is already playing, skip this one
# rather than cutting a sentence in half to announce an agent.
pgrep -x say >/dev/null 2>&1 && exit 0

printf '%s' "$type finished" | say -v Daniel -r 190 -f -
exit 0

#!/bin/bash
# MessageDisplay hook: speak each block of a reply as it appears.
#
# Narration used to live on Stop, which meant nothing was spoken until the whole
# turn finished. During a long piece of work that is silence followed by a
# summary. MessageDisplay fires once per block, carries the text in `delta`, and
# fires mid-turn, so speech keeps pace with the reply.
input=$(cat)

sid=$(jq -r '.session_id // ""' <<<"$input")
mode=$(bash "$(dirname "$0")/../lib/mode.sh" "$sid")
[[ "$mode" == narrate || "$mode" == converse ]] || exit 0

# Stay quiet while another app is playing.
pmset -g assertions 2>/dev/null | grep -q 'named: "Playing audio"' && exit 0

text=$(jq -r '.delta // ""' <<<"$input")
[[ -z "${text// /}" ]] && exit 0

bash "$(dirname "$0")/../bin/voice-server.sh" 2>/dev/null
printf '%s' "$text" \
  | curl -sS --max-time 5 -X POST --data-binary @- \
      "http://127.0.0.1:${VOICE_PORT:-51100}/say" >/dev/null 2>&1
exit 0

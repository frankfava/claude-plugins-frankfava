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

# Media apps hold a "Playing audio" power assertion while they play. `say` does
# not, so this never sees itself.
if pmset -g assertions 2>/dev/null | grep -q 'named: "Playing audio"'; then
  exit 0
fi

text=$(jq -r '.last_assistant_message // ""' <<<"$input")
[[ -z "$text" ]] && exit 0

# Built with printf so a literal code fence never appears in this file.
fence=$(printf '\140\140\140')
text=$(printf '%s' "$text" \
  | awk -v f="$fence" 'index($0,f)==1 {b=!b; if (b) print " code block omitted "; next} !b' \
  | sed -E 's/`([^`]{1,40})`/\1/g' \
  | sed -E 's/`[^`]*`/ code /g' \
  | sed -E 's/\(\)//g' \
  | sed -E 's/\[([^]]*)\]\([^)]*\)/\1/g' \
  | sed -E 's|https?://[^ ]*| link |g' \
  | sed -E 's/^#+ //g' \
  | sed -E 's/\*\*([^*]*)\*\*/\1/g' \
  | sed -E 's/^[[:space:]]*[-*] /, /g' \
  | sed -E 's/[<>]/ /g' \
  | sed -E 's/(—|–)/, /g' \
  | tr -s '[:space:]' ' ')

[[ -z "${text// /}" ]] && exit 0

# A fast turn can finish while the previous sentence is still playing.
pkill -x say 2>/dev/null

# Text on stdin, never argv: a leading hyphen would be read as a flag.
printf '%s' "$text" | say -v Matilda -r 190 -f -

exit 0
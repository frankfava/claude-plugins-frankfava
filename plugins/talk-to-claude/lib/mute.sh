#!/bin/bash
# Shared mute policy. Exits 0 when the caller should stay silent, 1 when it may
# speak. Called as: bash mute.sh "$session_id"
#
# A flag file is either empty, meaning indefinite, or holds a unix timestamp on
# its first line, meaning it expires then. Expired flags delete themselves, so a
# timed mute needs no timer process to end it.

sid="$1"
dir="$HOME/.claude"

active() {
  local f="$1" until_ts
  [[ -f "$f" ]] || return 1
  until_ts=$(head -n1 "$f" 2>/dev/null | tr -dc '0-9')
  if [[ -n "$until_ts" ]] && (( $(date +%s) >= until_ts )); then
    rm -f "$f"
    return 1
  fi
  return 0
}

# An explicit per-session unmute wins over a mute-everywhere flag, so one window
# can be brought back without disturbing the rest.
[[ -n "$sid" ]] && active "$dir/.talk-to-claude-unmuted.$sid" && exit 1

active "$dir/.talk-to-claude-muted" && exit 0
[[ -n "$sid" ]] && active "$dir/.talk-to-claude-muted.$sid" && exit 0

exit 1

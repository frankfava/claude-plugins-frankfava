#!/bin/bash
# SessionStart hook: inject the speaking-style guidance, and tell the agent which
# mute flag belongs to this session.
#
# Mute is keyed by session id so that muting one window leaves the others alone.
# A single shared flag would both leak across open sessions and get cleared by
# whichever session happened to start last.

input=$(cat)
sid=$(jq -r '.session_id // ""' <<<"$input" 2>/dev/null)

# Sessions never resume under a new id, so this one's flag is always stale.
[[ -n "$sid" ]] && rm -f "$HOME/.claude/.talk-to-claude-muted.$sid"

# Flags from sessions that have long since closed.
find "$HOME/.claude" -maxdepth 1 -name '.talk-to-claude-muted.*' -mtime +1 -delete 2>/dev/null

cat "$(dirname "$0")/../context/session-context.md"

exit 0

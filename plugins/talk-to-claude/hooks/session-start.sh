#!/bin/bash
# SessionStart hook: inject the speaking-style guidance, and tell the agent which
# voice mode belongs to this session.
#
# Mode is per session and defaults to off, so a new window is silent until it
# is asked for. A global switch meant every session inherited a decision made
# in a different one, which is how two of them ended up talking at once.

input=$(cat)
sid=$(jq -r '.session_id // ""' <<<"$input" 2>/dev/null)

# Sessions never resume under a new id, so this one's mode is always stale.
source "$(dirname "$0")/../lib/data-dir.sh"
[[ -n "$sid" ]] && rm -f "$(data_dir)/mode.$sid"

# Modes belonging to sessions that have long since closed.
find "$(data_dir)" -maxdepth 1 -name 'mode.*' -mtime +1 -delete 2>/dev/null

# MCP connects at session start, so the server has to exist by now.
bash "$(dirname "$0")/../bin/voice-server.sh" >/dev/null 2>&1 &

cat "$(dirname "$0")/../context/session-context.md"

exit 0

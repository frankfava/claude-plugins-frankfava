#!/bin/bash
# The voice mode for one session. Print it and exit; callers decide what to do.
#
#   off       silent, and does not listen. The default, so a new session never
#             starts talking over one you already have going.
#   narrate   speaks replies
#   listen    stays silent, listens after each reply
#   converse  both
#
# One file per session and nothing global. A global switch means every new
# session inherits a decision made in a different window, which is the whole
# problem this replaces.
sid="${1:-}"
file="$HOME/.claude/.talk-to-claude-mode.$sid"
[[ -n "$sid" && -f "$file" ]] && head -n1 "$file" | tr -d '[:space:]' || echo off

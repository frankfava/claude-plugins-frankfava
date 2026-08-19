#!/bin/bash
# The voice mode for one session. Print it and exit; callers decide what to do.
#
#   off       silent, and does not listen. The default, so a new session never
#             starts talking over one you already have going.
#   narrate   speaks replies
#   listen    stays silent, listens after each reply
#   converse  both
#
# One file per session, in the plugin's own data directory. Nothing global: a
# global switch means every new session inherits a decision made in a different
# window, which is the problem this replaces.
source "$(dirname "${BASH_SOURCE[0]}")/data-dir.sh"
sid="${1:-}"
file="$(data_dir)/mode.$sid"
[[ -n "$sid" && -f "$file" ]] && head -n1 "$file" | tr -d '[:space:]' || echo off

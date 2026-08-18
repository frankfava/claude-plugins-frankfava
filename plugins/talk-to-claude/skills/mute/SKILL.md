---
name: mute
description: Silence or restore the spoken replies from the talk-to-claude plugin. Use when the user asks to mute, unmute, go quiet, stop talking, be silent, turn the voice off or back on, or asks for quiet for a set period such as an hour.
---

# Muting spoken replies

Speech is controlled by flag files. Write or delete one, then confirm in text. `SID` is this session's id, given at the end of the session context.

| Intent | Action |
|---|---|
| Mute this session | `touch ~/.claude/.talk-to-claude-muted.SID` |
| Mute every session | `touch ~/.claude/.talk-to-claude-muted` |
| Unmute | delete the matching file |
| Unmute here while everything is muted | `touch ~/.claude/.talk-to-claude-unmuted.SID` |

Prefer the per-session flag unless the user says everywhere. It never outlives its session, because the SessionStart hook clears it.

## Time limits

An empty flag file means indefinite. To expire one, write a unix timestamp as its first line:

    date -v+1H +%s > ~/.claude/.talk-to-claude-muted.SID

Expired flags delete themselves on the next turn, so nothing needs scheduling and nothing needs cleaning up. Mute-everywhere persists until deleted, so offer a duration when the user does not name one.

## Checking

`lib/mute.sh` in this plugin is the policy. Run it with a session id to see what the hooks will do: exit 0 means silence, exit 1 means speak.

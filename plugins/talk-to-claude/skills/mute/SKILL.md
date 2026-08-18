---
name: mute
description: Silence or restore the spoken replies from the talk-to-claude plugin. Use when the user asks to mute, unmute, go quiet, stop talking, be silent, turn the voice off or back on, or asks for quiet for a set period such as an hour.
---

# Muting spoken replies

Run `bin/voice-mute.sh` in this plugin. Do not write flag files by hand, and never reuse a session id you saw earlier: a branched or resumed session gets a new one, and the script resolves the live id itself.

| Intent | Command |
|---|---|
| Mute here | `voice-mute.sh on` |
| Mute here for an hour | `voice-mute.sh on 3600` |
| Unmute here | `voice-mute.sh off` |
| Mute everything | `voice-mute.sh global-on` |
| Unmute everything | `voice-mute.sh global-off` |
| Speak here while everything is muted | `voice-mute.sh here` |
| What is in force | `voice-mute.sh status` |

Muting stops Claude speaking. It does not release the microphone, which is held open so it can hear you the moment you start. If the user asks about the microphone specifically, or wants the recording indicator gone, that is a different switch:

| Intent | Command |
|---|---|
| Release the microphone | `bin/voice-mic.sh off` |
| Take it back | `bin/voice-mic.sh on` |
| Is it open | `bin/voice-mic.sh status` |

Turning it off stops listening entirely, so hands-free will not hear anything until it is back on.

Prefer the per-session form unless the user says everywhere. Report what `status` says rather than what you expect, then confirm in text.

Muting everywhere persists until it is lifted or expires, so offer a duration when the user does not name one. A per-session mute is cleared when that session next starts.

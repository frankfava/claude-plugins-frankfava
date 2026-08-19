---
name: voice
description: Set how this session uses speech. Off is silent, narrate reads replies aloud, listen waits for you to speak after each reply, and converse does both. Use when the user asks to mute, unmute, go quiet, stop talking, talk, go hands free, use voice mode, read replies aloud, or listen for their answer.
---

# Voice mode

One setting per session, four values. Read or change it with `bin/voice-mode.sh`:

| Mode | Speaks | Listens |
| --- | --- | --- |
| `off` | no | no |
| `narrate` | yes | no |
| `listen` | no | yes |
| `converse` | yes | yes |

    bash bin/voice-mode.sh            # what is it now
    bash bin/voice-mode.sh converse   # set it

Report the result in plain language and nothing else. "Converse mode is on, so I will speak and listen." Do not mention hooks, flags, files or servers.

Off is the default, so a new session is silent until asked. Nothing here is global: setting a mode in one window never changes another, which is what stops two sessions talking over each other.

## Mapping what the user says

"Mute", "be quiet", "stop talking" mean `off` unless they are clearly only turning off the speaking half, in which case `listen`. "Unmute" means `narrate` unless they were in converse before. "Let's talk" and "go hands free" mean `converse`. "I'll read, you listen" means `listen`.

If it is genuinely ambiguous, set the narrower one and say which you picked.

## While speaking is on

Write the reply to the terminal first, then speak it. The user should be able to read what they are about to hear, and if they interrupt, they have already seen it.

Keep the spoken version to one to three sentences, with no markdown, lists, file paths or URLs. Write the full answer as usual and speak a summary.

## While listening is on

The microphone opens by itself after every reply, so do not call `listen` yourself. Whatever the user says arrives as the next thing you read, even if the turn took twenty minutes of work.

Print each exchange as it happens: exactly what came back from the microphone, and exactly what you sent to the speaker. An edited transcript is a summary wearing a transcript's clothes, and the mis-transcriptions are usually the interesting part.

It stops when the user sets the mode to off, or says goodbye, or says nothing at all, since the microphone gives up after a few seconds of silence.

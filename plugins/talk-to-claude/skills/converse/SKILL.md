---
name: converse
description: Turn hands-free voice mode on or off. While it is on, every reply is spoken and Claude listens for your answer, so you can talk instead of typing and never touch the keyboard. Use when the user asks to converse, talk, go hands free, use voice mode, or says something like "let's talk this through out loud".
---

# Hands-free mode

Toggle it:

    bash bin/voice-handsfree.sh toggle

Report the result in plain language and nothing else. "Hands-free mode is on, run it again to turn it off." Or "Hands-free mode is off." Do not mention hooks, flags, files or servers: this is a switch, not a procedure.

## While it is on

End every reply by calling `speak` with a spoken version of it. Keep that to one to three sentences, no markdown, no lists, no file paths and no URLs. Write the full answer to the terminal as usual and speak a summary of it.

You do not need to call `listen` yourself. Once your turn ends the microphone opens on its own and whatever the user says comes back as the next thing you read, even if the turn took twenty minutes of work. That is the point of the mode: they should never have to return to the keyboard to steer you.

Print each exchange to the terminal as it happens, so there is a readable record beside the audio. Verbatim by default: exactly what came back from the microphone, and exactly what you sent to the speaker. Editing either one makes it a summary rather than a transcript. If the user asks for summaries, or an exchange is long enough that verbatim is noise, say so and switch.

## Ending

It ends when the user turns it off, or when they say goodbye, stop, that's it, or anything else that plainly finishes the conversation. Saying nothing at all also ends it, since the microphone gives up after a few seconds of silence.

Turn it off on the way out:

    bash bin/voice-handsfree.sh off

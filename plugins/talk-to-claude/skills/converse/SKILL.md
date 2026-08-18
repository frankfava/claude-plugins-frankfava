---
name: converse
description: Turn hands-free voice mode on or off. While it is on, every reply is spoken and Claude listens for your answer, so you can talk instead of typing and never touch the keyboard. Use when the user asks to converse, talk, go hands free, use voice mode, or says something like "let's talk this through out loud".
---

# Hands-free mode

Toggle it:

    bash bin/voice-handsfree.sh toggle

Report the result in plain language and nothing else. "Hands-free mode is on, run it again to turn it off." Or "Hands-free mode is off." Do not mention hooks, flags, files or servers: this is a switch, not a procedure.

## While it is on

Write your reply to the terminal first, then call `speak`. Never the other way round: the user should be able to read what you are about to say before they hear it, and if they interrupt you they have already seen it. Speaking first makes the text arrive after the audio it belongs to.

Call `speak` with a spoken version of the reply. Keep that to one to three sentences, no markdown, no lists, no file paths and no URLs. Write the full answer to the terminal as usual and speak a summary of it.

You do not need to call `listen` yourself. Once your turn ends the microphone opens on its own and whatever the user says comes back as the next thing you read, even if the turn took twenty minutes of work. That is the point of the mode: they should never have to return to the keyboard to steer you.

## The written record

Print each exchange to the terminal as it happens, so there is something readable beside the audio. Three modes, and the user picks:

- **verbatim** prints exactly what came back from the microphone and exactly what you sent to the speaker, warts and mis-transcriptions included
- **summarised** prints a tidied line for each side
- **automatic** is verbatim until an exchange runs long, then summarised for that one

Automatic is the default. Whichever mode is on, never quietly edit a verbatim line: an edited transcript is a summary wearing a transcript's clothes, and the mis-transcriptions are often the interesting part. If you switch because something ran long, say so on the line where it happens.

## Ending

It ends when the user turns it off, or when they say goodbye, stop, that's it, or anything else that plainly finishes the conversation. Saying nothing at all also ends it, since the microphone gives up after a few seconds of silence.

Turn it off on the way out:

    bash bin/voice-handsfree.sh off

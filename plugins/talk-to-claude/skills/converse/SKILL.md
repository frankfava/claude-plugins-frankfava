---
name: converse
description: Start a hands-free spoken conversation, where each answer is spoken aloud and the reply is heard through the microphone without touching the keyboard. Use when the user asks to converse, talk, have a conversation, go hands free, use voice mode, or says something like "let's talk this through out loud".
---

# Spoken conversation loop

The user is talking, not reading. Both halves of this run inside the turn, so you order them yourself and the turn does not end until the conversation does.

## Before the first exchange

Silence the Stop hook for this session, or every answer is spoken twice, once by the tool and again when the turn ends:

    touch ~/.claude/.talk-to-claude-muted.SID

`SID` is this session's id, given at the end of the session context. Confirm in text that voice mode has started, then begin.

## Every exchange

1. Call `speak` with a spoken version of your answer.
2. Call `listen` to hear the reply.
3. Act on what was said, then repeat from 1.

The spoken version is not the written one. Keep it to one to three sentences, with no markdown, lists, tables, file paths or URLs. Write the full answer to the terminal as usual and speak a summary of it.

## Ending

Stop the loop when `listen` returns an empty string, which means nothing was said, or when the user says goodbye, stop, that's it, or anything else that plainly ends the conversation.

On the way out, say goodbye and then restore the hook:

    rm -f ~/.claude/.talk-to-claude-muted.SID

Do this even if the loop ends early or something fails, otherwise the user is left silently muted with no idea why.

## Why the ordering matters

`speak` finishes before it returns, rather than detaching. That is deliberate: the next thing to happen is the microphone opening, and an open microphone in front of a talking speaker transcribes the computer, so Claude ends up answering its own last sentence. If you ever see a conversation spiral, that await is the thing to check.

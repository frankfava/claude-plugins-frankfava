# talk-to-claude

Claude Code speaks its answers, and can listen for yours.

Two halves that work independently. A `Stop` hook reads each reply aloud, and an
MCP server exposes `speak` and `listen` as tools so a conversation can run
without the keyboard.

## Requirements

macOS. Speech uses the built-in `say`, and transcription uses whisper.cpp
through Metal, neither of which has a Windows equivalent here.

- [`jq`](https://jqlang.github.io/jq/) for the hooks
- [`uv`](https://docs.astral.sh/uv/) for the MCP server, which resolves its own
  Python dependencies on first run
- Microphone permission, granted to your terminal application rather than to
  Claude Code

## Install

```bash
claude plugin marketplace add frankfava/talk-to-claude
claude plugin install talk-to-claude@talk-to-claude
```

Restart Claude Code. Hooks load at startup and MCP servers connect at session
start, so a running session will not pick it up.

## What it does

Replies are read aloud after each turn, with markdown flattened first: code
blocks are announced rather than read, links become their text, and headings and
emphasis are dropped.

A session-start hook tells Claude it is being heard, which matters more than any
voice setting. Answers get shorter and stop arriving as tables.

Two MCP tools are registered. `speak` reads text aloud, and `listen` records
until you stop talking, then transcribes locally. Together they let Claude run
its own conversational loop, since both live inside the turn.

## Muting

Say "mute" and Claude writes a flag file the hooks check.

- This session only: `~/.claude/.talk-to-claude-muted.<session-id>`, cleared when
  that session next starts
- Everywhere: `~/.claude/.talk-to-claude-muted`, which persists until deleted
- One session back on while muted everywhere:
  `~/.claude/.talk-to-claude-unmuted.<session-id>`

Write a unix timestamp into any of those to have it expire; leave it empty for
indefinite. Expired flags delete themselves.

Speech also stands down on its own while another app is playing audio, so it
will not talk over music.

## Transcription

The `listen` tool uses whisper.cpp on Metal. It will borrow the
`distil-large-v3.5` model if Spokenly has already downloaded one, and otherwise
downloads `large-v3-turbo` itself on first use. Nothing is sent anywhere.

## Credits

Built alongside a tutorial on hooks and MCP servers in Claude Code.

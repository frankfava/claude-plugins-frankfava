# talk-to-claude

Claude Code speaks its answers, listens for yours, and gets out of the way when you want to type.

Three things, each usable on its own. Replies are read aloud after every turn. `speak` and `listen` are MCP tools, so Claude can hold a conversation inside a single turn. And hands-free mode opens the microphone when a turn ends, so you can talk instead of typing without ever touching the keyboard.

Everything runs through one long-lived local server, which is what makes it fast: models load once rather than on every reply.

## Requirements

macOS, for now. Speech and transcription both have local paths that lean on Apple hardware.

- [`uv`](https://docs.astral.sh/uv/) for the server, which resolves its own Python dependencies on first run
- [`jq`](https://jqlang.github.io/jq/) and `curl` for the hooks
- `espeak-ng` for the local voice: `brew install espeak-ng`
- Microphone permission, granted to your terminal application rather than to Claude Code
- A Deepgram API key at `~/.claude/.deepgram-key` if you want hosted transcription, which is the default

First run downloads a voice model, a few hundred megabytes, and takes a minute.

## Install

```bash
claude plugin marketplace add frankfava/talk-to-claude
claude plugin install talk-to-claude@talk-to-claude
```

Restart Claude Code. Hooks reload on demand, but MCP servers connect at session start and a transport change is only read at launch.

## Talking

Say "let's talk" or run `/talk-to-claude:converse` to toggle hands-free mode. It reports on or off in plain language, and running it again turns it off.

While it is on, every reply is spoken and the microphone opens when the turn ends. That includes turns where Claude went away and did twenty minutes of work, because it is driven by a hook rather than by Claude remembering. You never have to return to the keyboard to steer it.

You can talk over the top of an answer. Speech interrupts the speaker mid-sentence and what you said becomes the next thing Claude reads, which is how interrupting a person works. This only behaves on headphones: through laptop speakers the microphone hears the synthesiser, so set `VOICE_BARGE=0` there.

Each exchange is printed to the terminal as it happens, verbatim by default.

## Muting, and the microphone

Say "mute" and Claude writes a flag the hooks check. `bin/voice-mute.sh` is the underlying command: `on`, `off`, `global-on`, `global-off`, `here` to speak in one session while everything else is quiet, and `status` to see what is in force. Any of them takes a duration in seconds.

Muting stops Claude speaking. It does not release the microphone, which is held open so it can hear you the moment you start. That is a separate switch:

```bash
bin/voice-mic.sh off      # releases the device; the recording indicator goes away
bin/voice-mic.sh on
```

Speech also stands down on its own while another app is playing audio, so it will not talk over music.

## Voice and transcription

Speaking uses [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) by default, an 82M parameter model that runs locally and sounds nothing like a system voice. Audio starts playing while the rest of the sentence is still being synthesised, so a reply begins in under a second rather than after it.

Transcription uses Deepgram by default, which is faster than running a model locally and keeps the server under 200MB instead of nearly two gigabytes.

Both are swappable, and nothing above them cares which is in use:

| | Options | Variable |
|---|---|---|
| Speaking | `kokoro`, `deepgram`, `say` | `VOICE_TTS` |
| Transcription | `deepgram`, `whispercpp` | `VOICE_STT` |

`whispercpp` runs on Metal and will borrow Spokenly's `distil-large-v3.5` weights if they are already on disk, otherwise downloading its own. Choose it when you would rather no audio left the machine.

Other knobs: `VOICE_TTS_VOICE`, `VOICE_TTS_SPEED`, `VOICE_TTS_GAIN`, `VOICE_PORT`, `VOICE_IDLE_UNLOAD`, `VOICE_NO_SPEECH`, `VOICE_CONTINUOUS`, `VOICE_BARGE_THRESHOLD`.

## Hearing you in a noisy room

The microphone is held open, so the server learns the room continuously and sets its speech threshold from the current noise floor rather than from a constant. That removes the pause before listening, and means your own voice cannot poison the calibration by arriving during it.

Speech has to be sustained to count. A single loud block is a door or a cup, so a run of them is required before a turn starts, and half a second of speech before silence is allowed to end one. Without both, a noise starts a recording and the silence timer ends it before you have opened your mouth.

## How this differs from `/voice`

Claude Code ships a `/voice` command. It is dictation: you hold space, speak, and your words land in the prompt. It replaces typing.

This adds the other direction. `/voice` cannot speak an answer back, and nothing in it lets Claude open the microphone itself. Every dictation tool works the same way, macOS dictation and Windows Voice Typing included: you decide to speak, and the audio becomes text you were going to type anyway.

The difference that matters is where listening happens. `listen` runs inside the turn, so Claude can ask something and wait for the answer without the turn ending, and hands-free mode listens after the turn without you asking. That is a conversation rather than a sequence of dictated prompts.

They compose. Dictate a long prompt with `/voice` and let this read the reply back.

## Known gaps

Hands-free has been used for a full conversation, but not yet through a turn where Claude goes away and does real work first. That is the case it was built for and it is untested.

The barge-in threshold was measured in a cafe through AirPods, where a voice reads about 0.018 and the speaker bleed about 0.010. That gap is narrow and device specific, so it wants remeasuring at a desk.

Two sessions can both claim the speaker, since muting is per session and the server is shared. Mute the others for now.

## Credits

Built alongside a tutorial on hooks and MCP servers in Claude Code.

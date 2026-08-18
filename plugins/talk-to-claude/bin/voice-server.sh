#!/bin/bash
# Start the voice server if nothing is listening yet, then wait for it.
# Every caller runs this first, so whoever gets there first pays the startup.
PORT="${VOICE_PORT:-51100}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${TMPDIR:-/tmp}/talk-to-claude-voice.$PORT.log"

listening() { nc -z 127.0.0.1 "$PORT" 2>/dev/null; }

if ! listening; then
  # nohup rather than a job: this must outlive the hook that started it.
  VOICE_PORT="$PORT" nohup uv run "$ROOT/voice/server.py" --http >>"$LOG" 2>&1 &
  for _ in $(seq 1 60); do
    listening && break
    sleep 0.5
  done
fi

listening || { echo "voice server did not come up, see $LOG" >&2; exit 1; }

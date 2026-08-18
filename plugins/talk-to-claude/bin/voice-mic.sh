#!/bin/bash
# Release or reacquire the microphone without stopping the server.
PORT="${VOICE_PORT:-51100}"
case "${1:-status}" in
  on|off) q="?state=$1" ;;
  status) q="" ;;
  *) echo "usage: voice-mic.sh on|off|status" >&2; exit 2 ;;
esac
curl -sS --max-time 5 -X POST "http://127.0.0.1:$PORT/mic$q"; echo

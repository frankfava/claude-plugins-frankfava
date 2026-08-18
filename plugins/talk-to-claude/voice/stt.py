"""Transcription backends. One interface, local or hosted behind it.

`whispercpp` runs on Metal and keeps a model resident, which is why the server
is long-lived. `deepgram` sends the audio away instead, which costs a key and
a network round trip but nothing in memory. Pick with VOICE_STT.
"""

import os
import threading
import time
from pathlib import Path

import audio

BACKEND = os.environ.get("VOICE_STT", "whispercpp")
IDLE_UNLOAD = float(os.environ.get("VOICE_IDLE_UNLOAD", "900"))

# Borrowed rather than duplicated: these are ordinary GGML weights under a
# permissive licence, and a second 1.5GB copy earns nothing.
SPOKENLY_MODEL = (Path.home() / "Library/Application Support/Spokenly/Models"
                  / "whisper-ggml-distil-large-v3.5.bin")
FALLBACK_MODEL = "large-v3-turbo"

DEEPGRAM_KEY_FILE = Path.home() / ".claude/.deepgram-key"
DEEPGRAM_MODEL = os.environ.get("VOICE_STT_MODEL", "nova-3")

_model = None
_ready = threading.Event()
_last_used = time.monotonic()


def _load() -> None:
    global _model
    from pywhispercpp.model import Model
    target = str(SPOKENLY_MODEL) if SPOKENLY_MODEL.exists() else FALLBACK_MODEL
    _model = Model(target)
    _ready.set()


def _reap() -> None:
    """Give the weights back after a stretch of silence; reload on demand."""
    global _model
    while True:
        time.sleep(60)
        if _model is not None and time.monotonic() - _last_used > IDLE_UNLOAD:
            _model, _ = None, _ready.clear()


def _whispercpp(pcm) -> str:
    global _last_used
    _last_used = time.monotonic()
    if _model is None and not _ready.is_set():
        threading.Thread(target=_load, daemon=True).start()
    _ready.wait()
    return " ".join(s.text for s in _model.transcribe(pcm, language="en")).strip()


def _deepgram(pcm) -> str:
    import httpx

    key = DEEPGRAM_KEY_FILE.read_text().strip()
    r = httpx.post(
        "https://api.deepgram.com/v1/listen",
        params={"model": DEEPGRAM_MODEL, "smart_format": "true"},
        headers={"Authorization": f"Token {key}", "Content-Type": "audio/wav"},
        content=audio.to_wav(pcm),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["results"]["channels"][0]["alternatives"][0]["transcript"].strip()


BACKENDS = {"whispercpp": _whispercpp, "deepgram": _deepgram}

if BACKEND == "whispercpp":
    threading.Thread(target=_load, daemon=True).start()
    threading.Thread(target=_reap, daemon=True).start()


def transcribe(pcm) -> str:
    return BACKENDS[BACKEND](pcm)

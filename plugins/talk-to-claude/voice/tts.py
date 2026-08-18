"""Speaking backends. `say` needs nothing; kokoro needs a warm process.

Kokoro yields audio in chunks as it synthesises, so playback starts on the first
chunk rather than after the last. That turns a second of silence into about a
fifth of one, which is the difference between a reply that lands and a reply
that pauses first.
"""

import os
import subprocess
import threading

import numpy as np

SAMPLE_RATE = 24000          # what Kokoro emits
VOICE = os.environ.get("VOICE_TTS_VOICE", "bm_lewis")
BACKEND = os.environ.get("VOICE_TTS", "kokoro")

_pipeline = None
_ready = threading.Event()
_stop = threading.Event()


def _load() -> None:
    global _pipeline
    try:
        from kokoro import KPipeline
        _pipeline = KPipeline(lang_code=VOICE[0])   # 'b' British, 'a' American
    except Exception:
        _pipeline = None                            # fall back to `say`
    _ready.set()


if BACKEND == "kokoro":
    threading.Thread(target=_load, daemon=True).start()
else:
    _ready.set()


def interrupt() -> None:
    """Stop whatever is currently playing. The new utterance always wins."""
    _stop.set()
    subprocess.run(["pkill", "-x", "say"], capture_output=True)


def _say(text: str) -> str:
    subprocess.run(["say", "-v", "Daniel", "-r", "190", "-f", "-"],
                   input=text.encode("utf-8"), capture_output=True)
    return f"spoke {len(text)} characters with say"


def _kokoro(text: str) -> str:
    import sounddevice as sd

    _ready.wait()
    if _pipeline is None:
        return _say(text)

    _stop.clear()
    played = 0
    with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as out:
        for _, _, chunk in _pipeline(text, voice=VOICE):
            if _stop.is_set():
                break
            audio = np.asarray(chunk, dtype="float32").reshape(-1)
            out.write(audio)
            played += audio.size
    return f"spoke {played / SAMPLE_RATE:.1f}s with kokoro"


def speak_text(text: str) -> str:
    interrupt()
    return _kokoro(text) if BACKEND == "kokoro" else _say(text)

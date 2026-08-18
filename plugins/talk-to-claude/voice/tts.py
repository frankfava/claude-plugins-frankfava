"""Speaking backends. `say` needs nothing; kokoro needs a warm process.

Kokoro yields audio in chunks as it synthesises, so playback starts on the first
chunk rather than after the last. That turns a second of silence into about a
fifth of one, which is the difference between a reply that lands and a reply
that pauses first.
"""

import os
import subprocess
import threading
from pathlib import Path

import numpy as np

SPEAKING = Path(os.environ.get("TMPDIR", "/tmp")) / "talk-to-claude-speaking"

SAMPLE_RATE = 24000          # what Kokoro emits
VOICE = os.environ.get("VOICE_TTS_VOICE", "bm_lewis")
SAY_VOICE = os.environ.get("VOICE_SAY_VOICE", "Matilda")
SPEED = float(os.environ.get("VOICE_TTS_SPEED", "1.15"))
# Kokoro peaks around 0.47, so there is roughly 2x of headroom before clipping.
GAIN = float(os.environ.get("VOICE_TTS_GAIN", "2.0"))
BACKEND = os.environ.get("VOICE_TTS", "kokoro")

DEEPGRAM_KEY_FILE = Path.home() / ".claude/.deepgram-key"
DEEPGRAM_VOICE = os.environ.get("VOICE_TTS_MODEL", "aura-2-arcas-en")

_pipeline = None
_ready = threading.Event()

# A shared stop flag races: the incoming call clears it before the outgoing one
# checks it, and you hear both. A counter cannot race, because each utterance
# only ever compares its own number against the latest.
_generation = 0
_gen_lock = threading.Lock()


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


def _claim() -> int:
    """Take the next generation. Anything older stops at its next chunk."""
    global _generation
    with _gen_lock:
        _generation += 1
        return _generation


def interrupt() -> None:
    """Stop whatever is currently playing. The new utterance always wins."""
    _claim()
    subprocess.run(["pkill", "-x", "say"], capture_output=True)


def _say(text: str) -> str:
    subprocess.run(["say", "-v", SAY_VOICE, "-r", "190", "-f", "-"],
                   input=text.encode("utf-8"), capture_output=True)
    return f"spoke {len(text)} characters with say"


def _kokoro(text: str, mine: int) -> str:
    import sounddevice as sd

    _ready.wait()
    if _pipeline is None:
        return _say(text)

    played = 0
    with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as out:
        for _, _, chunk in _pipeline(text, voice=VOICE, speed=SPEED):
            if mine != _generation:          # someone newer is speaking
                break
            audio = np.asarray(chunk, dtype="float32").reshape(-1)
            if GAIN != 1.0:
                audio = np.clip(audio * GAIN, -1.0, 1.0)
            # Write in slices rather than whole chunks. Kokoro chunks by
            # sentence, so checking only between chunks means a long sentence
            # cannot be interrupted at all, which defeats barge-in.
            slice_size = SAMPLE_RATE // 5           # 200 ms
            for i in range(0, audio.size, slice_size):
                if mine != _generation:
                    break
                piece = audio[i:i + slice_size]
                out.write(piece)
                played += piece.size
            if mine != _generation:
                break
    return f"spoke {played / SAMPLE_RATE:.1f}s with kokoro"


def _deepgram(text: str, mine: int) -> str:
    """Hosted synthesis. No model resident, but the audio leaves the machine."""
    import httpx
    import sounddevice as sd

    key = DEEPGRAM_KEY_FILE.read_text().strip()
    r = httpx.post(
        "https://api.deepgram.com/v1/speak",
        params={"model": DEEPGRAM_VOICE, "encoding": "linear16", "sample_rate": "24000"},
        headers={"Authorization": f"Token {key}", "Content-Type": "application/json"},
        json={"text": text},
        timeout=60,
    )
    r.raise_for_status()
    pcm = np.frombuffer(r.content, dtype="<i2").astype("float32") / 32767
    if mine != _generation:
        return "superseded"
    sd.play(np.clip(pcm * GAIN, -1.0, 1.0), 24000)
    sd.wait()
    return f"spoke {len(pcm)/24000:.1f}s with deepgram"


BACKENDS = {
    "say": lambda text, mine: _say(text),
    "kokoro": _kokoro,
    "deepgram": _deepgram,
}


def speak_text(text: str) -> str:
    """Speak, publishing a flag so other hooks can tell we are mid-sentence."""
    mine = _claim()
    subprocess.run(["pkill", "-x", "say"], capture_output=True)
    SPEAKING.touch()
    try:
        return BACKENDS[BACKEND](text, mine)
    finally:
        if mine == _generation:
            SPEAKING.unlink(missing_ok=True)

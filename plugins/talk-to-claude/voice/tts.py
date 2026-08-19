"""Speaking backends. `say` needs nothing; kokoro needs a warm process.

Kokoro yields audio in chunks as it synthesises, so playback starts on the first
chunk rather than after the last. That turns a second of silence into about a
fifth of one, which is the difference between a reply that lands and a reply
that pauses first.
"""

import os
import queue
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

# How many utterances are in flight. A generation check cannot clear the flag,
# because the utterance that gets interrupted is by definition no longer the
# current generation, so it skips its own cleanup and the flag sticks forever.
# A stuck flag keeps the barge threshold raised and stops the no-speech clock,
# which presents as recordings that never end.
_speaking = 0
_speak_lock = threading.Lock()

# Narration arrives one block at a time, so utterances queue rather than
# interrupt. Interrupting was right when a whole reply was one utterance and a
# newer reply should win; with per-block narration it would leave you hearing
# only the last paragraph of everything.
_queue: "queue.Queue[str | None]" = queue.Queue()


def other_app_playing() -> bool:
    """True while another application is playing audio.

    Media apps hold a "Playing audio" power assertion for as long as they play.
    Neither Kokoro nor `say` raises one, so this never sees itself. It lives
    here rather than in a hook because a hook only guards its own caller, and
    anything posting straight to the server would talk over your music.
    """
    try:
        out = subprocess.run(["pmset", "-g", "assertions"], capture_output=True,
                             text=True, timeout=2).stdout
    except Exception:
        return False
    return 'named: "Playing audio"' in out


def _mark_speaking(delta: int) -> None:
    global _speaking
    with _speak_lock:
        _speaking += delta
        if _speaking > 0:
            SPEAKING.touch()
        elif SPEAKING.exists():
            SPEAKING.unlink(missing_ok=True)


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
    """Stop playing and drop what is queued behind it."""
    _claim()
    clear()
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


def _drain() -> None:
    """Play queued utterances in order, one at a time."""
    while True:
        text = _queue.get()
        if text is None:
            continue
        try:
            _play(text)
        except Exception:
            pass                    # a failed utterance must not kill the queue
        finally:
            _queue.task_done()


threading.Thread(target=_drain, daemon=True).start()


def enqueue(text: str) -> str:
    """Queue an utterance. Used by narration, which arrives block by block."""
    if other_app_playing():
        return "not speaking: another app is playing audio"
    _queue.put(text)
    return f"queued {len(text)} characters"


def clear() -> None:
    """Drop anything waiting. Barge-in stops the whole reply, not one block."""
    while not _queue.empty():
        try:
            _queue.get_nowait()
            _queue.task_done()
        except queue.Empty:
            break


def _play(text: str) -> str:
    """Speak, publishing a flag so other hooks can tell we are mid-sentence."""
    mine = _claim()
    subprocess.run(["pkill", "-x", "say"], capture_output=True)
    _mark_speaking(1)
    try:
        return BACKENDS[BACKEND](text, mine)
    finally:
        _mark_speaking(-1)

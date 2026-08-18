# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp<2", "sounddevice", "numpy", "pywhispercpp", "kokoro"]
# ///
"""Local MCP server exposing voice as tools. Runs on macOS and Windows."""

import asyncio
import os
import re
import time
import sys
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from mcp.server.fastmcp import FastMCP
from pywhispercpp.model import Model

sys.path.insert(0, str(Path(__file__).parent))
import tts   # noqa: E402  (needs the path above)

mcp = FastMCP("voice")


# Speech is a tool now, so it no longer passes through the hooks that own the
# mute flags. Only the global flag is reachable from here: a tool call carries
# no session id, so per-session mute stays a hook concern.
GLOBAL_MUTE = Path.home() / ".claude/.talk-to-claude-muted"

SAMPLE_RATE = 16000
BLOCK = 1600            # 0.1 s
THRESHOLD = 0.015       # RMS amplitude that counts as speech

# whisper.cpp reaches Metal and the Neural Engine, which the CTranslate2 path
# cannot do on a Mac. Borrow Spokenly's download rather than keep a second copy
# of the same 1.5GB weights; fall back to a model pywhispercpp fetches itself.
SPOKENLY_MODEL = (Path.home() / "Library/Application Support/Spokenly/Models"
                  / "whisper-ggml-distil-large-v3.5.bin")
FALLBACK_MODEL = "large-v3-turbo"

_model = None
_model_ready = threading.Event()
_last_used = time.monotonic()
IDLE_UNLOAD = float(os.environ.get("VOICE_IDLE_UNLOAD", "900"))   # seconds


def _load_model() -> None:
    global _model
    target = str(SPOKENLY_MODEL) if SPOKENLY_MODEL.exists() else FALLBACK_MODEL
    _model = Model(target)
    _model_ready.set()


# Loading costs about nine seconds. Start it at boot so the wait lands before
# anyone speaks rather than in the silence after the first utterance.
threading.Thread(target=_load_model, daemon=True).start()


def _reap() -> None:
    """Drop the transcription model after a stretch of silence.

    It reloads on demand, so the cost of being wrong is one slow call rather
    than a permanent 1.5GB of resident memory on a laptop.
    """
    global _model
    while True:
        time.sleep(60)
        if _model is not None and time.monotonic() - _last_used > IDLE_UNLOAD:
            _model = None
            _model_ready.clear()


threading.Thread(target=_reap, daemon=True).start()


def _transcribe(audio: "np.ndarray") -> str:
    global _last_used
    _last_used = time.monotonic()
    if _model is None and not _model_ready.is_set():
        threading.Thread(target=_load_model, daemon=True).start()
    _model_ready.wait()
    return " ".join(s.text for s in _model.transcribe(audio, language="en")).strip()


def _record(silence_seconds: float, max_seconds: float = 120.0):
    frames, started, silent_for, elapsed = [], False, 0.0, 0.0
    step = BLOCK / SAMPLE_RATE
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="float32", blocksize=BLOCK) as stream:
        while elapsed < max_seconds:
            data, _ = stream.read(BLOCK)
            elapsed += step
            level = float(np.sqrt(np.mean(data ** 2)))
            if level > THRESHOLD:
                started, silent_for = True, 0.0
                frames.append(data.copy())
            elif started:
                silent_for += step
                frames.append(data.copy())
                if silent_for >= silence_seconds:
                    break
    return np.concatenate(frames).flatten() if frames else np.array([], "float32")


def strip_markup(text: str) -> str:
    # \x60 is a backtick, written as an escape so this file can sit inside a
    # markdown fence without closing it.
    def inline(m, limit=40):
        inner = m.group(1)
        if len(inner) > limit:
            return " code "                     # long spans are commands, not names
        inner = re.sub(r"\(\s*\)", "", inner)   # strip_markup() -> strip markup
        return inner.replace("_", " ")          # max_seconds -> max seconds

    text = re.sub(r"\x60{3}.*?\x60{3}", " code block omitted ", text, flags=re.S)
    text = re.sub(r"\x60([^\x60]*)\x60", inline, text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", " link ", text)
    text = re.sub(r"^#+ ", "", text, flags=re.M)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", ", ", text, flags=re.M)
    text = re.sub(r"[<>]", " ", text)
    text = re.sub(r"[\u2014\u2013]", ", ", text)
    return re.sub(r"\s+", " ", text).strip()


@mcp.tool()
async def speak(text: str) -> str:
    """Read text aloud to the user through the computer's speakers.

    Pass a spoken version of your answer, not the answer itself: one to three
    sentences, no markdown, no paths or URLs. Write the full reply to the
    terminal as usual and speak a summary of it. Markup is stripped before
    speaking, so formatting is wasted rather than harmful.
    """
    if GLOBAL_MUTE.exists():
        return "muted"

    spoken = strip_markup(text)
    if not spoken:
        return "nothing to speak"

    # Awaited rather than detached: the next thing to happen is the microphone
    # opening, and an open mic in front of a talking speaker transcribes the
    # computer.
    return await asyncio.to_thread(tts.speak_text, spoken)


@mcp.tool()
async def listen(silence_seconds: float = 1.5) -> str:
    """Record until the user stops talking, then transcribe.

    Returns an empty string when the user says nothing, which is the
    signal to end the conversation.
    """
    audio = await asyncio.to_thread(_record, silence_seconds)
    if audio.size < SAMPLE_RATE // 2:
        return ""
    return await asyncio.to_thread(_transcribe, audio)


# Serving over HTTP rather than stdio is what lets the hooks reach the same
# warm process Claude Code is talking to. Loading a model per invocation is the
# thing this exists to avoid.
HOST = os.environ.get("VOICE_HOST", "127.0.0.1")
PORT = int(os.environ.get("VOICE_PORT", "51100"))

if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.settings.host = HOST
        mcp.settings.port = PORT
        mcp.run(transport="streamable-http")
    else:
        mcp.run()

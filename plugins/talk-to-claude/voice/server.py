# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp<2", "sounddevice", "numpy", "pywhispercpp"]
# ///
"""Local MCP server exposing voice as tools. Runs on macOS and Windows."""

import asyncio
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from mcp.server.fastmcp import FastMCP
from pywhispercpp.model import Model

mcp = FastMCP("voice")

MACOS = sys.platform == "darwin"
VOICE = "Daniel" if MACOS else "Microsoft Zira Desktop"
RATE = "190" if MACOS else "1"
PS1 = Path.home() / ".claude/voice/say.ps1"

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


def _load_model() -> None:
    global _model
    target = str(SPOKENLY_MODEL) if SPOKENLY_MODEL.exists() else FALLBACK_MODEL
    _model = Model(target)
    _model_ready.set()


# Loading costs about nine seconds. Start it at boot so the wait lands before
# anyone speaks rather than in the silence after the first utterance.
threading.Thread(target=_load_model, daemon=True).start()


def _transcribe(audio: "np.ndarray") -> str:
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

    if MACOS:
        subprocess.run(["pkill", "-x", "say"], capture_output=True)
        cmd = ["say", "-v", VOICE, "-r", RATE, "-f", "-"]
    else:
        cmd = [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(PS1), "-Voice", VOICE, "-Rate", RATE,
        ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    # Text on stdin on both platforms, never argv. Awaited rather than
    # detached, which matters as soon as a microphone is involved.
    await proc.communicate(spoken.encode("utf-8"))
    return f"spoke {len(spoken)} characters"


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

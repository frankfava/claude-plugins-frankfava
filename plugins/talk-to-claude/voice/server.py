# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp<2", "sounddevice", "numpy", "pywhispercpp", "kokoro", "httpx"]
# ///
"""Local MCP server exposing voice as tools. Runs on macOS and Windows."""

import asyncio
import os
import re
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse
sys.path.insert(0, str(Path(__file__).parent))
import audio  # noqa: E402  (all three need the path above)
import stt    # noqa: E402
import tts    # noqa: E402

mcp = FastMCP("voice")


# Speech is a tool now, so it no longer passes through the hooks that own the
# mute flags. Only the global flag is reachable from here: a tool call carries
# no session id, so per-session mute stays a hook concern.
GLOBAL_MUTE = Path.home() / ".claude/.talk-to-claude-muted"

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
    pcm = await asyncio.to_thread(audio.record, silence_seconds, 120.0, tts.interrupt)
    if pcm.size < audio.SAMPLE_RATE // 2:
        return ""
    return await asyncio.to_thread(stt.transcribe, pcm)


# Serving over HTTP rather than stdio is what lets the hooks reach the same
# warm process Claude Code is talking to. Loading a model per invocation is the
# thing this exists to avoid.
HOST = os.environ.get("VOICE_HOST", "127.0.0.1")
PORT = int(os.environ.get("VOICE_PORT", "51100"))

@mcp.custom_route("/say", methods=["POST"])
async def http_say(request: Request) -> PlainTextResponse:
    """Speak text posted as the request body, and return without waiting.

    The hooks use this rather than the MCP tool. Speaking MCP costs a Python
    interpreter and a handshake per turn; a POST costs a socket. Returning
    immediately keeps the hook from blocking the turn for the length of the
    sentence, which is what `async: true` exists for elsewhere.
    """
    if GLOBAL_MUTE.exists():
        return PlainTextResponse("muted")

    text = strip_markup((await request.body()).decode("utf-8"))
    if not text:
        return PlainTextResponse("nothing to speak")

    asyncio.create_task(asyncio.to_thread(tts.speak_text, text))
    return PlainTextResponse("speaking")


@mcp.custom_route("/listen", methods=["POST"])
async def http_listen(request: Request) -> PlainTextResponse:
    """Record and transcribe, for callers that are not Claude.

    The hands-free hook uses this. It exists so the loop survives me forgetting
    to call the tool: the harness fires the hook when a turn ends, whatever I
    was doing beforehand.
    """
    try:
        seconds = float(request.query_params.get("silence", "1.5"))
    except ValueError:
        seconds = 1.5
    pcm = await asyncio.to_thread(audio.record, seconds, 120.0, tts.interrupt)
    if pcm.size < audio.SAMPLE_RATE // 2:
        return PlainTextResponse("")
    return PlainTextResponse(await asyncio.to_thread(stt.transcribe, pcm))


@mcp.custom_route("/mic", methods=["POST"])
async def http_mic(request: Request) -> PlainTextResponse:
    """Turn the held-open input stream on or off, or report it."""
    return PlainTextResponse(audio.microphone(request.query_params.get("state")))


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.settings.host = HOST
        mcp.settings.port = PORT
        mcp.run(transport="streamable-http")
    else:
        mcp.run()

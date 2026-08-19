"""This session's voice mode, for the server side.

The hooks read it through lib/mode.sh with a session id handed to them. The
server has no session id, so it resolves the live one the same way the CLI
does: the transcript being written to right now.
"""

from pathlib import Path

DIR = Path.home() / ".claude"


def live_session() -> str:
    files = sorted(DIR.glob("projects/*/*.jsonl"), key=lambda f: f.stat().st_mtime,
                   reverse=True)
    return files[0].stem if files else ""


def current() -> str:
    sid = live_session()
    if not sid:
        return "off"
    f = DIR / f".talk-to-claude-mode.{sid}"
    return f.read_text().strip().split("\n")[0] if f.exists() else "off"


def may_speak() -> bool:
    return current() in ("narrate", "converse")


def may_listen() -> bool:
    return current() in ("listen", "converse")

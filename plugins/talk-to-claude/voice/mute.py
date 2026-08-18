"""Mute policy, shared by the tools and the HTTP routes.

The hooks get this from lib/mute.sh. The server had its own half of it, which
only knew about the global flag, so a session that had been unmuted explicitly
still could not speak through a tool. One rule, two callers.
"""

import time
from pathlib import Path

DIR = Path.home() / ".claude"


def live_session() -> str:
    """The transcript being written to now. A value captured earlier goes stale
    the moment a session is branched or resumed."""
    files = sorted(DIR.glob("projects/*/*.jsonl"), key=lambda f: f.stat().st_mtime,
                   reverse=True)
    return files[0].stem if files else ""


def _active(path: Path) -> bool:
    """A flag counts unless it names an expiry that has passed."""
    if not path.exists():
        return False
    head = path.read_text(errors="ignore").strip().split("\n")[0]
    digits = "".join(c for c in head if c.isdigit())
    if digits and time.time() >= int(digits):
        path.unlink(missing_ok=True)
        return False
    return True


def silent(session: str | None = None) -> bool:
    sid = session if session is not None else live_session()
    if sid and _active(DIR / f".talk-to-claude-unmuted.{sid}"):
        return False                     # explicit override beats a global mute
    if _active(DIR / ".talk-to-claude-muted"):
        return True
    return bool(sid) and _active(DIR / f".talk-to-claude-muted.{sid}")

from __future__ import annotations

import re
from typing import Final

_MAX_REPLY_CHARS: Final[int] = 1200
_MIN_REPLY_CHARS: Final[int] = 2


def heuristic_reply_ok(reply: str, *, customer_text: str) -> bool:
    """
    Fast local checks before (and regardless of) an LLM judge call.

    Keeps obviously bad model output from reaching WhatsApp.
    """
    t = (reply or "").strip()
    if len(t) < _MIN_REPLY_CHARS or len(t) > _MAX_REPLY_CHARS:
        return False
    if "```" in t:
        return False
    # Avoid pure echo of the entire customer blob (weak models sometimes do this).
    c = (customer_text or "").strip()
    if c and t.lower() == c.lower():
        return False
    if not re.search(r"\w", t):
        return False
    return True

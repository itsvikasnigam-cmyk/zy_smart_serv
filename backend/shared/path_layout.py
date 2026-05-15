from __future__ import annotations

import os
from pathlib import Path

from backend.shared.config import settings


def zy_base_dir() -> Path:
    """
    Blueprint §10: configurable base for logs, exports, and caches (no hardcoded ``C:\\`` paths).

    Resolution: ``ZY_BASE_DIR`` env → ``settings.zy_base_dir`` → ``~/.zy-smart-serv``.
    """
    raw = (os.environ.get("ZY_BASE_DIR") or settings.zy_base_dir or "").strip()
    if raw:
        base = Path(raw).expanduser()
    else:
        base = Path.home() / ".zy-smart-serv"
    base.mkdir(parents=True, exist_ok=True)
    return base


def zy_logs_dir() -> Path:
    d = zy_base_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def zy_exports_dir() -> Path:
    d = zy_base_dir() / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d

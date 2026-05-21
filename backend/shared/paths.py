"""Filesystem roots for logs, exports, and models (Option C — no hardcoded C:\\ paths)."""

from __future__ import annotations

import os
from pathlib import Path

from .config import settings


def zy_base_dir() -> Path:
    """
    Active workspace root. Dev: repo on C: (via ZY_BASE_DIR or cwd).
    Prod: set ZY_BASE_DIR to D:\\zy-smart-ai (or your install folder) when you move.
    """
    raw = (settings.zy_base_dir or os.environ.get("ZY_BASE_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    # Fallback: repo root (parent of backend/)
    return Path(__file__).resolve().parents[2]


def zy_subdir(name: str) -> Path:
    p = zy_base_dir() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def logs_dir() -> Path:
    return zy_subdir("logs")


def exports_dir() -> Path:
    return zy_subdir("exports")


def models_dir() -> Path:
    return zy_subdir("models")


def ollama_vendor_dir() -> Path:
    """Project-local Ollama binaries (Gate 2). Populated by scripts/setup_ollama_local.ps1."""
    return zy_base_dir() / "vendor" / "ollama"


def ollama_models_dir() -> Path:
    """OLLAMA_MODELS root — moves with ZY_BASE_DIR (e.g. D:\\zy-smart-ai\\models\\ollama)."""
    p = models_dir() / "ollama"
    p.mkdir(parents=True, exist_ok=True)
    return p

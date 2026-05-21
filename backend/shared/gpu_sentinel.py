"""Chat Y: GPU VRAM sentinel state (Redis keys or local file fallback).

Keys when Redis is enabled (default prefix ``gpu:4090``):
  - ``gpu:4090:status`` — AVAILABLE | BUSY | OFFLINE
  - ``gpu:4090:updated_at`` — ISO timestamp
  - ``gpu:4090:owner`` — optional lease holder
  - ``gpu:4090:note`` — optional human note

Ollama on :11435 is unchanged; this is coordination metadata for dual-GPU / WSL tracks.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from backend.shared.config import Settings, settings
from backend.shared.paths import zy_base_dir
from backend.shared.redis_client import get_redis_client, redis_feature_enabled

log = logging.getLogger("gpu_sentinel")

GpuStatus = Literal["AVAILABLE", "BUSY", "OFFLINE"]
_VALID: tuple[str, ...] = ("AVAILABLE", "BUSY", "OFFLINE")


@dataclass(frozen=True)
class GpuSentinelState:
    status: GpuStatus
    updated_at: str
    owner: str | None = None
    note: str | None = None
    source: str = "default"


def _redis_prefix(cfg: Settings) -> str:
    return (getattr(cfg, "gpu_redis_key_prefix", None) or "gpu:4090").strip().rstrip(":")


def _key(prefix: str, suffix: str) -> str:
    return f"{prefix}:{suffix}"


def _state_file(cfg: Settings | None = None) -> Path:
    c = cfg or settings
    sub = (getattr(c, "gpu_sentinel_state_file", None) or "logs/gpu_sentinel_state.json").strip()
    return zy_base_dir() / sub


def _read_file_state(path: Path) -> GpuSentinelState | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    st = str(data.get("status") or "").upper()
    if st not in _VALID:
        return None
    return GpuSentinelState(
        status=st,  # type: ignore[arg-type]
        updated_at=str(data.get("updated_at") or ""),
        owner=data.get("owner"),
        note=data.get("note"),
        source="file",
    )


def _write_file_state(path: Path, state: GpuSentinelState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": state.status,
                "updated_at": state.updated_at,
                "owner": state.owner,
                "note": state.note,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def get_gpu_sentinel_state(cfg: Settings | None = None) -> GpuSentinelState:
    """Read sentinel state; defaults to AVAILABLE (Ollama path safe)."""
    c = cfg or settings
    prefix = _redis_prefix(c)
    if redis_feature_enabled(c):
        client = get_redis_client(c)
        if client:
            try:
                st = (client.get(_key(prefix, "status")) or "AVAILABLE").strip().upper()
                if st not in _VALID:
                    st = "AVAILABLE"
                return GpuSentinelState(
                    status=st,  # type: ignore[arg-type]
                    updated_at=str(client.get(_key(prefix, "updated_at")) or ""),
                    owner=client.get(_key(prefix, "owner")),
                    note=client.get(_key(prefix, "note")),
                    source="redis",
                )
            except Exception:
                log.debug("redis gpu sentinel read failed", exc_info=True)

    file_state = _read_file_state(_state_file(c))
    if file_state:
        return file_state
    return GpuSentinelState(
        status="AVAILABLE",
        updated_at="",
        source="default",
    )


def set_gpu_sentinel_state(
    status: GpuStatus,
    *,
    owner: str | None = None,
    note: str | None = None,
    force: bool = False,
    cfg: Settings | None = None,
) -> GpuSentinelState:
    """
    Set GPU status. Without ``force``, refuses to overwrite BUSY held by another owner.
    """
    c = cfg or settings
    st = status.upper()  # type: ignore[assignment]
    if st not in _VALID:
        raise ValueError(f"invalid status: {status}")

    current = get_gpu_sentinel_state(c)
    new_owner = (owner or "").strip() or None
    if (
        not force
        and current.status == "BUSY"
        and st == "BUSY"
        and current.owner
        and new_owner
        and current.owner != new_owner
    ):
        raise PermissionError(f"GPU held by {current.owner}; use --force to override")

    now = datetime.now(timezone.utc).isoformat()
    out = GpuSentinelState(status=st, updated_at=now, owner=new_owner, note=(note or "").strip() or None)

    prefix = _redis_prefix(c)
    if redis_feature_enabled(c):
        client = get_redis_client(c)
        if client:
            try:
                pipe = client.pipeline()
                pipe.set(_key(prefix, "status"), st)
                pipe.set(_key(prefix, "updated_at"), now)
                if new_owner:
                    pipe.set(_key(prefix, "owner"), new_owner)
                else:
                    pipe.delete(_key(prefix, "owner"))
                if out.note:
                    pipe.set(_key(prefix, "note"), out.note)
                else:
                    pipe.delete(_key(prefix, "note"))
                pipe.execute()
                return replace(out, source="redis")
            except Exception:
                log.debug("redis gpu sentinel write failed", exc_info=True)

    _write_file_state(_state_file(c), out)
    return replace(out, source="file")

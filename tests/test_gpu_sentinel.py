from __future__ import annotations

import json
from pathlib import Path

from backend.shared.config import Settings
from backend.shared.gpu_sentinel import (
    get_gpu_sentinel_state,
    set_gpu_sentinel_state,
)


def test_file_fallback_busy_available(tmp_path: Path, monkeypatch) -> None:
    cfg = Settings(
        redis_enabled=False,
        gpu_sentinel_state_file=str(tmp_path / "gpu.json"),
    )
    monkeypatch.setattr("backend.shared.gpu_sentinel.settings", cfg)
    monkeypatch.setattr("backend.shared.gpu_sentinel._state_file", lambda _c=None: tmp_path / "gpu.json")

    out = set_gpu_sentinel_state("BUSY", owner="test", note="job", cfg=cfg)
    assert out.status == "BUSY"
    assert out.source == "file"

    read = get_gpu_sentinel_state(cfg)
    assert read.status == "BUSY"
    assert read.owner == "test"

    set_gpu_sentinel_state("AVAILABLE", force=True, cfg=cfg)
    assert get_gpu_sentinel_state(cfg).status == "AVAILABLE"


def test_default_available_when_no_state(tmp_path: Path, monkeypatch) -> None:
    cfg = Settings(
        redis_enabled=False,
        gpu_sentinel_state_file=str(tmp_path / "missing.json"),
    )
    monkeypatch.setattr("backend.shared.gpu_sentinel.settings", cfg)
    monkeypatch.setattr("backend.shared.gpu_sentinel._state_file", lambda _c=None: tmp_path / "missing.json")

    st = get_gpu_sentinel_state(cfg)
    assert st.status == "AVAILABLE"
    assert st.source == "default"

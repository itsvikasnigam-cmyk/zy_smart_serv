"""GPU sentinel CLI — report or set AVAILABLE/BUSY/OFFLINE (Chat Y).

Usage:
  python backend/tools/gpu_sentinel_cli.py status
  python backend/tools/gpu_sentinel_cli.py set-available
  python backend/tools/gpu_sentinel_cli.py set-busy --owner batch_processor --note "nightly job"
  python backend/tools/gpu_sentinel_cli.py set-offline --force
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.shared.gpu_sentinel import get_gpu_sentinel_state, set_gpu_sentinel_state


def main() -> int:
    p = argparse.ArgumentParser(description="GPU VRAM sentinel (gpu:4090:* Redis keys or file).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Print current sentinel state")

    for name, st in (
        ("set-available", "AVAILABLE"),
        ("set-busy", "BUSY"),
        ("set-offline", "OFFLINE"),
    ):
        sp = sub.add_parser(name, help=f"Set status to {st}")
        sp.add_argument("--owner", default=None)
        sp.add_argument("--note", default=None)
        sp.add_argument("--force", action="store_true")

    args = p.parse_args()

    if args.cmd == "status":
        state = get_gpu_sentinel_state()
        print(
            json.dumps(
                {
                    "status": state.status,
                    "updated_at": state.updated_at,
                    "owner": state.owner,
                    "note": state.note,
                    "source": state.source,
                },
                indent=2,
            )
        )
        return 0

    mapping = {
        "set-available": "AVAILABLE",
        "set-busy": "BUSY",
        "set-offline": "OFFLINE",
    }
    try:
        out = set_gpu_sentinel_state(
            mapping[args.cmd],  # type: ignore[arg-type]
            owner=args.owner,
            note=args.note,
            force=args.force,
        )
    except PermissionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "status": out.status, "source": out.source}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

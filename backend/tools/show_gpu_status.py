"""Print GPU sentinel state (alias for gpu_sentinel_cli status).

Usage:
  python backend/tools/show_gpu_status.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    cli = root / "backend" / "tools" / "gpu_sentinel_cli.py"
    return subprocess.call([sys.executable, str(cli), "status"])


if __name__ == "__main__":
    raise SystemExit(main())

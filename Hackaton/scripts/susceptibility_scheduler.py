"""Ejecuta el generador al iniciar y luego con el intervalo configurado."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402


def run_once() -> int:
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "build_susceptibility_map.py")])


def main() -> int:
    seconds = get_settings().susceptibility_refresh_seconds
    if seconds < 300:
        raise ValueError("SUSCEPTIBILITY_REFRESH_SECONDS debe ser al menos 300 segundos.")
    while True:
        status = run_once()
        if status:
            print(f"La actualización de susceptibilidad terminó con código {status}; se reintentará.", flush=True)
        time.sleep(seconds)


if __name__ == "__main__":
    raise SystemExit(main())

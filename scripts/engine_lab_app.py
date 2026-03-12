from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.engine.lab_app import run_engine_lab_app


if __name__ == "__main__":
    run_engine_lab_app()

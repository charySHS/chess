from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.engine.profile import current_engine_profile, default_snapshot_path, save_engine_profile


def main() -> None:
    path = default_snapshot_path()
    profile = current_engine_profile(name=path.stem)
    save_engine_profile(path, profile)
    print(f"saved snapshot to {path}")


if __name__ == "__main__":
    main()

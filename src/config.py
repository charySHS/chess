from __future__ import annotations

from dataclasses import dataclass
from os import getenv, environ
from pathlib import Path


def _load_dotenv() -> None:
    dotenv_path = Path(__file__).resolve().parents[1] / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        environ.setdefault(key, value)


_load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    theme_name: str = getenv("NEWCHESS_THEME", "glass")
    ui_backend: str = getenv("NEWCHESS_UI_BACKEND", "pygame")
    stockfish_path: str = getenv("NEWCHESS_STOCKFISH_PATH", "stockfish")
    stockfish_depth: int = int(getenv("NEWCHESS_STOCKFISH_DEPTH", "12"))
    model_path: Path = Path(getenv("NEWCHESS_MODEL_PATH", "artifacts/value_network.npz"))
    training_data_path: Path = Path(getenv("NEWCHESS_TRAINING_DATA", "data/stockfish_samples.jsonl"))

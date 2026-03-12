from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvaluatorConfig:
    material_weight: float = 1.0
    neural_weight: float = 1.0
    mobility_weight: float = 0.35
    passed_pawn_weight: float = 1.0
    rook_file_weight: float = 1.0
    king_safety_weight: float = 1.0
    endgame_king_weight: float = 1.0


@dataclass(frozen=True)
class SearchConfig:
    aspiration_window: float = 40.0
    null_move_reduction: int = 2
    null_move_depth_trigger: int = 3
    lmr_reduction: int = 1
    lmr_depth_trigger: int = 3
    lmr_move_index_trigger: int = 3
    delta_margin: float = 120.0
    max_killers: int = 2


@dataclass(frozen=True)
class EngineProfile:
    name: str = "current"
    search: SearchConfig = SearchConfig()
    evaluator: EvaluatorConfig = EvaluatorConfig()


def save_engine_profile(path: Path, profile: EngineProfile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")


def load_engine_profile(path: Path) -> EngineProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EngineProfile(
        name=payload.get("name", "loaded"),
        search=SearchConfig(**payload.get("search", {})),
        evaluator=EvaluatorConfig(**payload.get("evaluator", {})),
    )


def default_snapshot_path() -> Path:
    return Path("artifacts/engine_snapshots/baseline_v1.json")


def current_engine_profile(name: str = "current") -> EngineProfile:
    return EngineProfile(name=name)

from __future__ import annotations

import json
import re
import shutil
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
    model_path: str | None = None


def save_engine_profile(path: Path, profile: EngineProfile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")


def load_engine_profile(path: Path) -> EngineProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EngineProfile(
        name=payload.get("name", "loaded"),
        search=SearchConfig(**payload.get("search", {})),
        evaluator=EvaluatorConfig(**payload.get("evaluator", {})),
        model_path=payload.get("model_path"),
    )


def default_snapshot_path() -> Path:
    snapshots_dir = Path("artifacts/engine_snapshots")
    latest = latest_snapshot_path(snapshots_dir)
    return latest if latest is not None else snapshots_dir / "baseline_v1.json"


def current_engine_profile(name: str = "current") -> EngineProfile:
    return EngineProfile(name=name)


_SNAPSHOT_PATTERN = re.compile(r"^(?P<prefix>.+)_v(?P<version>\d+)$")


def latest_snapshot_path(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    candidates: list[tuple[int, Path]] = []
    for path in directory.glob("*.json"):
        match = _SNAPSHOT_PATTERN.match(path.stem)
        if match is None:
            continue
        candidates.append((int(match.group("version")), path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def next_snapshot_path(reference_path: Path) -> Path:
    directory = reference_path.parent
    directory.mkdir(parents=True, exist_ok=True)
    match = _SNAPSHOT_PATTERN.match(reference_path.stem)
    prefix = match.group("prefix") if match is not None else reference_path.stem
    highest = 0
    for path in directory.glob(f"{prefix}_v*.json"):
        candidate = _SNAPSHOT_PATTERN.match(path.stem)
        if candidate is None or candidate.group("prefix") != prefix:
            continue
        highest = max(highest, int(candidate.group("version")))
    return directory / f"{prefix}_v{highest + 1}.json"


def snapshot_model_path(snapshot_path: Path) -> Path:
    return snapshot_path.with_suffix(".npz")


def copy_snapshot_model(source_path: Path | None, target_snapshot_path: Path) -> Path | None:
    if source_path is None or not source_path.exists():
        return None
    target_path = snapshot_model_path(target_snapshot_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)
    return target_path


def resolve_snapshot_model_path(snapshot_path: Path, profile: EngineProfile | None = None) -> Path | None:
    if profile is not None and profile.model_path:
        declared = Path(profile.model_path)
        if not declared.is_absolute():
            declared = snapshot_path.parent / declared
        if declared.exists():
            return declared

    sibling = snapshot_model_path(snapshot_path)
    if sibling.exists():
        return sibling
    return None


def load_latest_engine_profile(directory: Path) -> tuple[EngineProfile, Path] | None:
    latest = latest_snapshot_path(directory)
    if latest is None:
        return None
    return load_engine_profile(latest), latest

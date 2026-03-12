from __future__ import annotations

from pathlib import Path

from src.chess_core import Board
from src.engine.profile import (
    EngineProfile,
    EvaluatorConfig,
    SearchConfig,
    load_engine_profile,
    load_latest_engine_profile,
    next_snapshot_path,
    save_engine_profile,
)
from src.engine.search import SearchEngine


def test_engine_profile_roundtrip(tmp_path: Path) -> None:
    profile = EngineProfile(
        name="test",
        search=SearchConfig(aspiration_window=25.0),
        evaluator=EvaluatorConfig(mobility_weight=0.5),
        model_path="baseline_v1.npz",
    )
    path = tmp_path / "profile.json"
    save_engine_profile(path, profile)
    loaded = load_engine_profile(path)

    assert loaded == profile


def test_search_engine_accepts_profile() -> None:
    engine = SearchEngine(profile=EngineProfile())
    result = engine.iterative_deepening(Board(), max_depth=1)

    assert result.best_move is not None


def test_snapshot_version_helpers_pick_latest(tmp_path: Path) -> None:
    first = tmp_path / "baseline_v1.json"
    second = tmp_path / "baseline_v2.json"
    save_engine_profile(first, EngineProfile(name="baseline_v1"))
    save_engine_profile(second, EngineProfile(name="baseline_v2"))

    latest = load_latest_engine_profile(tmp_path)

    assert latest is not None
    assert latest[1] == second
    assert latest[0].name == "baseline_v2"
    assert next_snapshot_path(first) == tmp_path / "baseline_v3.json"

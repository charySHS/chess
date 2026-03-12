from __future__ import annotations

from pathlib import Path

from src.chess_core import Board
from src.engine.profile import EngineProfile, EvaluatorConfig, SearchConfig, load_engine_profile, save_engine_profile
from src.engine.search import SearchEngine


def test_engine_profile_roundtrip(tmp_path: Path) -> None:
    profile = EngineProfile(
        name="test",
        search=SearchConfig(aspiration_window=25.0),
        evaluator=EvaluatorConfig(mobility_weight=0.5),
    )
    path = tmp_path / "profile.json"
    save_engine_profile(path, profile)
    loaded = load_engine_profile(path)

    assert loaded == profile


def test_search_engine_accepts_profile() -> None:
    engine = SearchEngine(profile=EngineProfile())
    result = engine.iterative_deepening(Board(), max_depth=1)

    assert result.best_move is not None

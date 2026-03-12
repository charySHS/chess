from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.chess_core import Board, generate_legal_moves, is_checkmate, is_stalemate
from src.chess_core.constants import BLACK, WHITE
from src.config import AppConfig
from src.engine.profile import (
    EngineProfile,
    copy_snapshot_model,
    current_engine_profile,
    next_snapshot_path,
    resolve_snapshot_model_path,
    save_engine_profile,
)
from src.engine.search import SearchEngine
from src.nn.dataset import TrainingSample, append_samples
from src.nn.trainer import TrainingSummary, train_value_network


OPENING_LINES = (
    (),
    ("e2e4", "e7e5", "g1f3"),
    ("d2d4", "d7d5", "c2c4"),
    ("c2c4", "e7e5", "g2g3"),
    ("g1f3", "d7d5", "c2c4"),
)

BENCHMARK_DEPTH = 4
BENCHMARK_RATING_GAMES = 20
BENCHMARK_SELFPLAY_GAMES = 10
BENCHMARK_MAX_PLIES = 100


@dataclass(frozen=True)
class LabConfig:
    snapshot_path: Path
    training_data_path: Path
    model_output_path: Path
    depth: int = 3
    rating_games: int = 6
    selfplay_games: int = 8
    max_plies: int = 120
    snapshot_name: str = "baseline_v1"
    take_snapshot: bool = False
    promote_snapshot_after_batch: bool = True
    train_model: bool = False
    learn_from_rating_matches: bool = True
    benchmark_mode: bool = False


@dataclass(frozen=True)
class MatchResult:
    current_score: float
    result: str
    plies: int
    samples: list[TrainingSample]


@dataclass(frozen=True)
class RatingSummary:
    score: float
    games: int
    average: float
    estimated_elo_diff: float


@dataclass(frozen=True)
class SelfPlaySummary:
    games: int
    samples_written: int
    output_path: Path


@dataclass(frozen=True)
class LabSummary:
    snapshot_path: Path
    snapshot_model_path: Path | None
    rating: RatingSummary
    selfplay: SelfPlaySummary
    training: TrainingSummary | None
    history_path: Path


ProgressCallback = Callable[[str], None]
EventCallback = Callable[[dict[str, object]], None]


@dataclass(frozen=True)
class RunHistoryEntry:
    timestamp: str
    snapshot_path: str
    snapshot_model_path: str | None
    depth: int
    rating_games: int
    selfplay_games: int
    max_plies: int
    take_snapshot: bool
    promote_snapshot_after_batch: bool
    train_model: bool
    learn_from_rating_matches: bool
    benchmark_mode: bool
    rating_score: float
    rating_average: float
    estimated_elo_diff: float
    selfplay_samples: int
    training_loss: float | None
    training_output_path: str | None


def default_history_path() -> Path:
    return Path("artifacts/engine_lab_history.jsonl")


def append_history_entry(path: Path, entry: RunHistoryEntry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(entry)) + "\n")


def load_history_entries(path: Path) -> list[RunHistoryEntry]:
    if not path.exists():
        return []
    entries: list[RunHistoryEntry] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            payload.setdefault("snapshot_model_path", None)
            payload.setdefault("promote_snapshot_after_batch", True)
            payload.setdefault("learn_from_rating_matches", False)
            payload.setdefault("benchmark_mode", False)
            entries.append(RunHistoryEntry(**payload))
    return entries


def benchmark_lab_config(config: LabConfig) -> LabConfig:
    return LabConfig(
        snapshot_path=config.snapshot_path,
        training_data_path=config.training_data_path,
        model_output_path=config.model_output_path,
        depth=BENCHMARK_DEPTH,
        rating_games=BENCHMARK_RATING_GAMES,
        selfplay_games=BENCHMARK_SELFPLAY_GAMES,
        max_plies=BENCHMARK_MAX_PLIES,
        snapshot_name=config.snapshot_name,
        take_snapshot=config.take_snapshot,
        promote_snapshot_after_batch=config.promote_snapshot_after_batch,
        train_model=config.train_model,
        learn_from_rating_matches=config.learn_from_rating_matches,
        benchmark_mode=True,
    )


def save_snapshot(path: Path, name: str, model_source_path: Path | None = None, progress: ProgressCallback | None = None) -> EngineProfile:
    frozen_model_path = copy_snapshot_model(model_source_path, path)
    profile = current_engine_profile(name=name)
    if frozen_model_path is not None:
        profile = EngineProfile(name=profile.name, search=profile.search, evaluator=profile.evaluator, model_path=frozen_model_path.name)
    save_engine_profile(path, profile)
    if progress is not None:
        progress(f"Saved snapshot profile to {path}")
    return profile


def promote_snapshot(
    reference_path: Path,
    name: str,
    model_source_path: Path | None = None,
    progress: ProgressCallback | None = None,
) -> tuple[EngineProfile, Path]:
    target_path = next_snapshot_path(reference_path)
    frozen_model_path = copy_snapshot_model(model_source_path, target_path)
    profile = current_engine_profile(name=target_path.stem if not name else target_path.stem)
    if frozen_model_path is not None:
        profile = EngineProfile(name=profile.name, search=profile.search, evaluator=profile.evaluator, model_path=frozen_model_path.name)
    save_engine_profile(target_path, profile)
    if progress is not None:
        progress(f"Promoted new batch snapshot to {target_path}")
    return profile, target_path


def apply_uci(board: Board, uci: str) -> None:
    move = next(move for move in generate_legal_moves(board) if move.uci() == uci)
    board.make_move(move)


def elo_from_score(score: float) -> float:
    score = min(0.99, max(0.01, score))
    return -400.0 * math.log10(1.0 / score - 1.0)


def _result_cp(winner: str | None, perspective: str) -> int:
    if winner is None:
        return 0
    return 1000 if winner == perspective else -1000


def _samples_from_positions(positions: list[tuple[str, str]], winner: str | None) -> list[TrainingSample]:
    return [TrainingSample(fen=fen, value_cp=_result_cp(winner, perspective)) for fen, perspective in positions]


def _current_model_source(config: LabConfig) -> Path | None:
    if config.model_output_path.exists():
        return config.model_output_path
    app_model_path = AppConfig().model_path
    if app_model_path.exists():
        return app_model_path
    return None


def play_game(
    current: SearchEngine,
    baseline: SearchEngine,
    depth: int,
    opening: tuple[str, ...],
    current_as_white: bool,
    max_plies: int,
    progress: ProgressCallback | None = None,
    event_callback: EventCallback | None = None,
    stage: str = "rating",
    game_index: int = 0,
    total_games: int = 1,
) -> MatchResult:
    board = Board()
    positions: list[tuple[str, str]] = []
    for uci in opening:
        apply_uci(board, uci)
        if event_callback is not None:
            event_callback(
                {
                    "type": "board",
                    "stage": stage,
                    "game_index": game_index + 1,
                    "games": total_games,
                    "fen": board.to_fen(),
                    "last_move": uci,
                    "ply": len(board.history),
                    "current_as_white": current_as_white,
                }
            )

    for ply in range(max_plies):
        if is_checkmate(board):
            winner = BLACK if board.side_to_move == WHITE else WHITE
            current_side = WHITE if current_as_white else BLACK
            return MatchResult(
                current_score=1.0 if winner == current_side else 0.0,
                result=f"{winner} mates",
                plies=ply,
                samples=_samples_from_positions(positions, winner),
            )
        if is_stalemate(board) or board.is_threefold_repetition():
            return MatchResult(current_score=0.5, result="draw", plies=ply, samples=_samples_from_positions(positions, None))

        current_to_move = (board.side_to_move == WHITE and current_as_white) or (board.side_to_move == BLACK and not current_as_white)
        engine = current if current_to_move else baseline
        positions.append((board.to_fen(), board.side_to_move))
        move = engine.choose_move(board, depth=depth)
        if move is None:
            return MatchResult(current_score=0.5, result="no move", plies=ply, samples=_samples_from_positions(positions, None))
        board.make_move(move)
        if event_callback is not None:
            event_callback(
                {
                    "type": "board",
                    "stage": stage,
                    "game_index": game_index + 1,
                    "games": total_games,
                    "fen": board.to_fen(),
                    "last_move": move.uci(),
                    "ply": len(board.history),
                    "current_as_white": current_as_white,
                }
            )

    return MatchResult(current_score=0.5, result="ply limit", plies=max_plies, samples=_samples_from_positions(positions, None))


def rate_current_vs_snapshot(
    snapshot_profile: EngineProfile,
    snapshot_path: Path,
    depth: int,
    games: int,
    max_plies: int,
    output_path: Path | None = None,
    progress: ProgressCallback | None = None,
    event_callback: EventCallback | None = None,
) -> RatingSummary:
    current_model_path = AppConfig().model_path
    baseline_model_path = resolve_snapshot_model_path(snapshot_path, snapshot_profile)
    current_engine = SearchEngine(profile=current_engine_profile("current"), model_path=current_model_path)
    baseline_engine = SearchEngine(profile=snapshot_profile, model_path=baseline_model_path)
    total_score = 0.0
    samples_written = 0

    for game_index in range(games):
        opening = OPENING_LINES[game_index % len(OPENING_LINES)]
        current_as_white = game_index % 2 == 0
        result = play_game(
            current_engine,
            baseline_engine,
            depth,
            opening,
            current_as_white,
            max_plies,
            progress=progress,
            event_callback=event_callback,
            stage="rating",
            game_index=game_index,
            total_games=games,
        )
        total_score += result.current_score
        if output_path is not None and result.samples:
            append_samples(output_path, result.samples)
            samples_written += len(result.samples)
        if progress is not None:
            color = "white" if current_as_white else "black"
            progress(
                f"Rating game {game_index + 1}/{games}: current={color} "
                f"score={result.current_score:.1f} result={result.result} plies={result.plies}"
            )
            if output_path is not None and result.samples:
                progress(f"Appended {len(result.samples)} rating samples to {output_path}")

    average = total_score / games if games else 0.5
    if progress is not None:
        progress(f"Rating complete: score={total_score:.1f}/{games} average={average:.3f}")
        if output_path is not None:
            progress(f"Rating sample generation complete: wrote {samples_written} samples to {output_path}")
    return RatingSummary(
        score=total_score,
        games=games,
        average=average,
        estimated_elo_diff=elo_from_score(average),
    )


def generate_selfplay_samples(
    snapshot_profile: EngineProfile,
    snapshot_path: Path,
    depth: int,
    games: int,
    max_plies: int,
    output_path: Path,
    progress: ProgressCallback | None = None,
    event_callback: EventCallback | None = None,
) -> SelfPlaySummary:
    current_model_path = AppConfig().model_path
    baseline_model_path = resolve_snapshot_model_path(snapshot_path, snapshot_profile)
    current_engine = SearchEngine(profile=current_engine_profile("current"), model_path=current_model_path)
    baseline_engine = SearchEngine(profile=snapshot_profile, model_path=baseline_model_path)
    samples_written = 0

    for game_index in range(games):
        board = Board()
        opening = OPENING_LINES[game_index % len(OPENING_LINES)]
        current_as_white = game_index % 2 == 0
        for uci in opening:
            apply_uci(board, uci)
            if event_callback is not None:
                event_callback(
                    {
                        "type": "board",
                        "stage": "selfplay",
                        "game_index": game_index + 1,
                        "games": games,
                        "fen": board.to_fen(),
                        "last_move": uci,
                        "ply": len(board.history),
                        "current_as_white": current_as_white,
                    }
                )

        positions: list[tuple[str, str]] = []
        winner: str | None = None

        for _ in range(max_plies):
            if is_checkmate(board):
                winner = BLACK if board.side_to_move == WHITE else WHITE
                break
            if is_stalemate(board) or board.is_threefold_repetition():
                winner = None
                break

            positions.append((board.to_fen(), board.side_to_move))
            current_to_move = (board.side_to_move == WHITE and current_as_white) or (board.side_to_move == BLACK and not current_as_white)
            engine = current_engine if current_to_move else baseline_engine
            move = engine.choose_move(board, depth=depth)
            if move is None:
                winner = None
                break
            board.make_move(move)
            if event_callback is not None:
                event_callback(
                    {
                        "type": "board",
                        "stage": "selfplay",
                        "game_index": game_index + 1,
                        "games": games,
                        "fen": board.to_fen(),
                        "last_move": move.uci(),
                        "ply": len(board.history),
                        "current_as_white": current_as_white,
                    }
                )

        game_samples = _samples_from_positions(positions, winner)
        if game_samples:
            append_samples(output_path, game_samples)
            samples_written += len(game_samples)

        if progress is not None:
            progress(
                f"Self-play game {game_index + 1}/{games}: positions={len(positions)} "
                f"winner={winner or 'draw'}"
            )
            progress(f"Appended {len(game_samples)} samples to {output_path}")

    if progress is not None:
        progress(f"Self-play complete: wrote {samples_written} samples to {output_path}")
    return SelfPlaySummary(games=games, samples_written=samples_written, output_path=output_path)


def run_lab_cycle(
    config: LabConfig,
    snapshot_profile: EngineProfile,
    progress: ProgressCallback | None = None,
    event_callback: EventCallback | None = None,
    history_path: Path | None = None,
) -> LabSummary:
    if config.benchmark_mode:
        config = benchmark_lab_config(config)

    active_snapshot_profile = snapshot_profile
    if config.take_snapshot:
        active_snapshot_profile = save_snapshot(
            config.snapshot_path,
            config.snapshot_name,
            model_source_path=_current_model_source(config),
            progress=progress,
        )

    if progress is not None:
        progress("Starting rating run")
    rating = rate_current_vs_snapshot(
        active_snapshot_profile,
        config.snapshot_path,
        config.depth,
        config.rating_games,
        config.max_plies,
        output_path=config.training_data_path if config.learn_from_rating_matches else None,
        progress=progress,
        event_callback=event_callback,
    )
    if progress is not None:
        progress("Starting self-play sample generation")
    selfplay = generate_selfplay_samples(
        active_snapshot_profile,
        config.snapshot_path,
        config.depth,
        config.selfplay_games,
        config.max_plies,
        config.training_data_path,
        progress=progress,
        event_callback=event_callback,
    )

    training: TrainingSummary | None = None
    if config.train_model:
        if progress is not None:
            progress("Starting value-network training")
        training = train_value_network(config.training_data_path, config.model_output_path)
        if progress is not None:
            progress(
                f"Training complete: epochs={training.epochs} samples={training.sample_count} "
                f"loss={training.final_loss:.6f} output={training.output_path}"
            )

    final_snapshot_path = config.snapshot_path
    final_snapshot_profile = active_snapshot_profile
    if config.promote_snapshot_after_batch:
        final_snapshot_profile, final_snapshot_path = promote_snapshot(
            config.snapshot_path,
            config.snapshot_name,
            model_source_path=_current_model_source(config),
            progress=progress,
        )
        if progress is not None:
            progress(f"Promoted current engine snapshot for next batch at {final_snapshot_path}")
        if event_callback is not None:
            event_callback(
                {
                    "type": "snapshot_promoted",
                    "path": str(final_snapshot_path),
                    "model_path": str(resolve_snapshot_model_path(final_snapshot_path, final_snapshot_profile) or ""),
                }
            )

    final_snapshot_model_path = resolve_snapshot_model_path(final_snapshot_path, final_snapshot_profile)

    resolved_history_path = history_path or default_history_path()
    append_history_entry(
        resolved_history_path,
        RunHistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            snapshot_path=str(final_snapshot_path),
            snapshot_model_path=str(final_snapshot_model_path) if final_snapshot_model_path is not None else None,
            depth=config.depth,
            rating_games=config.rating_games,
            selfplay_games=config.selfplay_games,
            max_plies=config.max_plies,
            take_snapshot=config.take_snapshot,
            promote_snapshot_after_batch=config.promote_snapshot_after_batch,
            train_model=config.train_model,
            learn_from_rating_matches=config.learn_from_rating_matches,
            benchmark_mode=config.benchmark_mode,
            rating_score=rating.score,
            rating_average=rating.average,
            estimated_elo_diff=rating.estimated_elo_diff,
            selfplay_samples=selfplay.samples_written,
            training_loss=training.final_loss if training is not None else None,
            training_output_path=str(training.output_path) if training is not None else None,
        ),
    )
    if event_callback is not None:
        event_callback({"type": "history_updated", "path": str(resolved_history_path)})

    return LabSummary(
        snapshot_path=final_snapshot_path,
        snapshot_model_path=final_snapshot_model_path,
        rating=rating,
        selfplay=selfplay,
        training=training,
        history_path=resolved_history_path,
    )

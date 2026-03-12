from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.chess_core import Board, generate_legal_moves, is_checkmate, is_stalemate
from src.chess_core.constants import BLACK, WHITE
from src.engine.profile import current_engine_profile, default_snapshot_path, load_engine_profile
from src.engine.search import SearchEngine


OPENING_LINES = (
    (),
    ("e2e4", "e7e5", "g1f3"),
    ("d2d4", "d7d5", "c2c4"),
    ("c2c4", "e7e5", "g2g3"),
    ("g1f3", "d7d5", "c2c4"),
)


@dataclass(frozen=True)
class MatchResult:
    current_score: float
    result: str
    plies: int


def apply_uci(board: Board, uci: str) -> None:
    move = next(move for move in generate_legal_moves(board) if move.uci() == uci)
    board.make_move(move)


def play_game(current: SearchEngine, baseline: SearchEngine, depth: int, opening: tuple[str, ...], current_as_white: bool, max_plies: int) -> MatchResult:
    board = Board()
    for uci in opening:
        apply_uci(board, uci)

    for ply in range(max_plies):
        if is_checkmate(board):
            winner = BLACK if board.side_to_move == WHITE else WHITE
            if current_as_white:
                current_side = WHITE
            else:
                current_side = BLACK
            current_score = 1.0 if winner == current_side else 0.0
            return MatchResult(current_score=current_score, result=f"{winner} mates", plies=ply)
        if is_stalemate(board) or board.is_threefold_repetition():
            return MatchResult(current_score=0.5, result="draw", plies=ply)

        current_to_move = (board.side_to_move == WHITE and current_as_white) or (board.side_to_move == BLACK and not current_as_white)
        engine = current if current_to_move else baseline
        move = engine.choose_move(board, depth=depth)
        if move is None:
            return MatchResult(current_score=0.5, result="no move", plies=ply)
        board.make_move(move)

    return MatchResult(current_score=0.5, result="ply limit", plies=max_plies)


def elo_from_score(score: float) -> float:
    score = min(0.99, max(0.01, score))
    return -400.0 * math.log10(1.0 / score - 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rate current engine against a frozen snapshot.")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--games", type=int, default=8)
    parser.add_argument("--max-plies", type=int, default=120)
    parser.add_argument("--snapshot", type=Path, default=default_snapshot_path())
    args = parser.parse_args()

    current_engine = SearchEngine(profile=current_engine_profile("current"))
    baseline_engine = SearchEngine(profile=load_engine_profile(args.snapshot))

    total_score = 0.0
    for game_index in range(args.games):
        opening = OPENING_LINES[game_index % len(OPENING_LINES)]
        current_as_white = game_index % 2 == 0
        result = play_game(current_engine, baseline_engine, args.depth, opening, current_as_white, args.max_plies)
        total_score += result.current_score
        color = "white" if current_as_white else "black"
        print(
            f"game {game_index + 1:02d} current={color:5s} opening={len(opening):d}ply "
            f"score={result.current_score:.1f} result={result.result} plies={result.plies}"
        )

    average = total_score / args.games if args.games else 0.5
    elo = elo_from_score(average)
    print(f"score={total_score:.1f}/{args.games} average={average:.3f} estimated_elo_diff={elo:.1f}")


if __name__ == "__main__":
    main()

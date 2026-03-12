from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.chess_core import Board, generate_legal_moves, is_checkmate, is_stalemate
from src.chess_core.constants import BLACK, WHITE
from src.engine.profile import current_engine_profile, default_snapshot_path, load_engine_profile
from src.engine.search import SearchEngine
from src.nn.dataset import TrainingSample, append_samples


OPENING_LINES = (
    (),
    ("e2e4", "e7e5", "g1f3"),
    ("d2d4", "d7d5", "c2c4"),
    ("c2c4", "e7e5", "g2g3"),
)


def apply_uci(board: Board, uci: str) -> None:
    move = next(move for move in generate_legal_moves(board) if move.uci() == uci)
    board.make_move(move)


def result_cp(winner: str | None, perspective: str) -> int:
    if winner is None:
        return 0
    return 1000 if winner == perspective else -1000


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate self-play samples from current vs snapshot engine.")
    parser.add_argument("--games", type=int, default=6)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--max-plies", type=int, default=120)
    parser.add_argument("--output", type=Path, default=Path("data/selfplay_snapshot_games.jsonl"))
    parser.add_argument("--snapshot", type=Path, default=default_snapshot_path())
    args = parser.parse_args()

    current_engine = SearchEngine(profile=current_engine_profile("current"))
    baseline_engine = SearchEngine(profile=load_engine_profile(args.snapshot))
    samples: list[TrainingSample] = []

    for game_index in range(args.games):
        board = Board()
        opening = OPENING_LINES[game_index % len(OPENING_LINES)]
        for uci in opening:
            apply_uci(board, uci)

        current_as_white = game_index % 2 == 0
        positions: list[tuple[str, str]] = []
        winner: str | None = None

        for _ in range(args.max_plies):
            if is_checkmate(board):
                winner = BLACK if board.side_to_move == WHITE else WHITE
                break
            if is_stalemate(board) or board.is_threefold_repetition():
                winner = None
                break

            positions.append((board.to_fen(), board.side_to_move))
            current_to_move = (board.side_to_move == WHITE and current_as_white) or (board.side_to_move == BLACK and not current_as_white)
            engine = current_engine if current_to_move else baseline_engine
            move = engine.choose_move(board, depth=args.depth)
            if move is None:
                winner = None
                break
            board.make_move(move)

        for fen, perspective in positions:
            samples.append(TrainingSample(fen=fen, value_cp=result_cp(winner, perspective)))

        print(f"game {game_index + 1:02d} samples={len(positions)} winner={winner or 'draw'}")

    append_samples(args.output, samples)
    print(f"wrote {len(samples)} samples to {args.output}")


if __name__ == "__main__":
    main()

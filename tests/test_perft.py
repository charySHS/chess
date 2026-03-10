from __future__ import annotations

from src.chess_core import Board
from tests.perft_harness import divide, perft


def test_starting_position_perft_targets() -> None:
    board = Board()
    targets = {
        1: 20,
        2: 400,
        3: 8902,
        4: 197281,
    }

    for depth, expected in targets.items():
        actual = perft(board, depth)
        print(f"perft({depth}) = {actual}")
        assert actual == expected


def test_starting_position_divide_depth_1_prints() -> None:
    board = Board()
    counts = divide(board, 1)

    print("divide(1):")
    for move_uci in sorted(counts):
        print(f"{move_uci}: {counts[move_uci]}")

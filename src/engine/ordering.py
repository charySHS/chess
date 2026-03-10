from __future__ import annotations

from src.chess_core import Move


PIECE_PRIORITY = {
    "p": 1,
    "n": 3,
    "b": 3,
    "r": 5,
    "q": 9,
    "k": 100,
    ".": 0,
}


def move_ordering_key(move: Move) -> tuple[int, int, int]:
    capture_score = PIECE_PRIORITY.get(move.captured.lower(), 0)
    promotion_score = PIECE_PRIORITY.get(move.promotion.lower(), 0) if move.promotion else 0
    return (capture_score, promotion_score, int(move.is_castling))


def order_moves(moves: list[Move]) -> list[Move]:
    return sorted(moves, key=move_ordering_key, reverse=True)

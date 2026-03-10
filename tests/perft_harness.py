from __future__ import annotations

from src.chess_core import Board, generate_legal_moves


def perft(board: Board, depth: int) -> int:
    if depth == 0:
        return 1

    nodes = 0
    for move in generate_legal_moves(board):
        board.make_move(move)
        nodes += perft(board, depth - 1)
        board.undo_move()

    return nodes


def divide(board: Board, depth: int) -> dict[str, int]:
    if depth < 1:
        return {}

    counts: dict[str, int] = {}
    for move in generate_legal_moves(board):
        board.make_move(move)
        counts[move.uci()] = perft(board, depth - 1)
        board.undo_move()

    return counts

from __future__ import annotations

from src.chess_core import Board, is_checkmate
from src.engine.search import SearchEngine


def test_search_finds_forced_mate_when_available() -> None:
    board = Board("7k/6Q1/5K2/8/8/8/8/8 w - - 0 1")

    move = SearchEngine().choose_move(board, depth=2)

    assert move is not None
    board.make_move(move)
    assert is_checkmate(board)


def test_search_uses_make_undo_without_corrupting_board_state() -> None:
    board = Board()
    start_fen = board.to_fen()
    start_hash = board.zobrist_key

    result = SearchEngine().iterative_deepening(board, max_depth=3)

    assert result.best_move is not None
    assert board.to_fen() == start_fen
    assert board.zobrist_key == start_hash

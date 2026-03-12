from __future__ import annotations

from src.chess_core import Board, generate_legal_moves


def test_make_undo_restores_start_position_for_all_root_moves() -> None:
    board = Board()
    start_fen = board.to_fen()
    start_white_king = board.white_king_pos
    start_black_king = board.black_king_pos
    start_hash = board.zobrist_key

    for move in generate_legal_moves(board):
        board.make_move(move)
        board.undo_move()

        assert board.to_fen() == start_fen
        assert board.white_king_pos == start_white_king
        assert board.black_king_pos == start_black_king
        assert board.zobrist_key == start_hash

from __future__ import annotations

from src.chess_core import Board, generate_legal_moves, is_in_check, is_square_attacked
from src.chess_core.constants import BLACK
from src.chess_core.move import square_to_index


def test_knight_attack_detection() -> None:
    board = Board("4k3/8/8/8/8/5n2/8/4K3 w - - 0 1")
    e1 = square_to_index("e1")

    assert is_square_attacked(board, e1, BLACK)
    assert is_in_check(board, "w")


def test_pawn_double_push_blocked() -> None:
    board = Board("4k3/8/8/8/8/4n3/4P3/4K3 w - - 0 1")
    legal_uci = {move.uci() for move in generate_legal_moves(board)}

    assert "e2e4" not in legal_uci


def test_en_passant_make_undo_roundtrip() -> None:
    board = Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    before_fen = board.to_fen()

    ep_move = next(move for move in generate_legal_moves(board) if move.uci() == "e5d6")
    board.make_move(ep_move)

    assert board.squares[square_to_index("d5")] == "."
    assert board.squares[square_to_index("d6")] == "P"

    board.undo_move()
    assert board.to_fen() == before_fen


def test_castling_requires_rook_presence() -> None:
    board = Board("4k3/8/8/8/8/8/8/4K3 w KQ - 0 1")
    legal_uci = {move.uci() for move in generate_legal_moves(board)}

    assert "e1g1" not in legal_uci
    assert "e1c1" not in legal_uci


def test_pawn_promotions_all_piece_types() -> None:
    board = Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
    legal_uci = {move.uci() for move in generate_legal_moves(board)}

    assert {"a7a8q", "a7a8r", "a7a8b", "a7a8n"}.issubset(legal_uci)

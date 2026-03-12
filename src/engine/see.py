from __future__ import annotations

from src.chess_core import Board, Move
from src.chess_core.constants import BLACK, EMPTY, PIECE_VALUES, WHITE
from src.chess_core.movegen import is_square_attacked


def piece_value(piece: str) -> int:
    if piece == EMPTY:
        return 0
    return abs(PIECE_VALUES[piece])


def static_exchange_eval(board: Board, move: Move) -> int:
    captured_value = piece_value(move.captured)
    moving_value = piece_value(move.piece)
    promotion_gain = 0
    if move.promotion is not None:
        promotion_gain = piece_value(move.promotion) - moving_value

    score = captured_value + promotion_gain
    side = WHITE if move.piece.isupper() else BLACK
    opponent = BLACK if side == WHITE else WHITE

    board.make_move(move)
    defended = is_square_attacked(board, move.to_square, opponent)
    board.undo_move()

    if defended:
        score -= moving_value
    return score

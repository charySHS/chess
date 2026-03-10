# chess_core/movegen.py

from __future__ import annotations

from typing import Iterable

from src.chess_core.board import Board
from src.chess_core.constants import WHITE, BLACK, EMPTY
from src.chess_core.move import Move, square_to_index


KNIGHT_DELTAS = [
    (-2, -1), (-2, 1),
    (-1, -2), (-1, 2),
    (1, -2), (1, 2),
    (2, -1), (2, 1),
]

KING_DELTAS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1), (0, 1),
    (1, -1), (1, 0), (1, 1)
]

BISHOP_DIRECTIONS = [
    (-1, -1), (-1, 1), (1, -1), (1, 1)
]

ROOK_DIRECTIONS = [
    (-1, 0), (1, 0), (0, -1), (0, 1)
]

QUEEN_DIRECTIONS = BISHOP_DIRECTIONS + ROOK_DIRECTIONS


# ----------------------------------------------------------
# -- Helper Functions
# ----------------------------------------------------------
def index_to_row_col(index: int) -> tuple[int, int]:
    return divmod(index, 8)

def row_col_to_index(row: int, col: int) -> int:
    return row * 8 + col

def on_board(row: int, col: int) -> bool:
    return 0 <= row < 8 and 0 <= col < 8

def opposite(side: str) -> str:
    return BLACK if side == WHITE else WHITE

def piece_belongs_to_enemy(piece: str, side: str) -> bool:
    if piece == EMPTY:
        return False

    return (side == WHITE and piece.islower()) or (side == BLACK and piece.isupper())

def piece_belongs_to_side(piece: str, side: str) -> bool:
    if piece == EMPTY:
        return False

    return (side == WHITE and piece.isupper()) or (side == BLACK and piece.islower())

def is_checkmate(board: Board, side: str | None = None) -> bool:
    if side is None:
        side = board.side_to_move

    return is_in_check(board, side) and not has_legal_moves(board, side)

def is_stalemate(board: Board, side: str | None = None) -> bool:
    if side is None:
        side = board.side_to_move

    return not is_in_check(board, side) and not has_legal_moves(board, side)

def is_in_check(board: Board, side: str | None = None) -> bool:
    if side is None:
        side = board.side_to_move

    king_square = board.white_king_pos if side == WHITE else board.black_king_pos

    return is_square_attacked(board, king_square, opposite(side))

def has_legal_moves(board: Board, side: str | None = None) -> bool:
    return len(generate_legal_moves(board, side)) > 0


# -------------------------------------------------------------
# -- Move Verification
# -------------------------------------------------------------

def generate_legal_moves(board: Board, side: str | None = None) -> list[Move]:
    if side is None:
        side = board.side_to_move

    legal_moves: list[Move] = []

    for move in generate_pseudo_legal_moves(board, side):
        board.make_move(move)
        still_in_check = is_in_check(board, side)
        board.undo_move()

        if not still_in_check:
            legal_moves.append(move)

    return legal_moves

def generate_pseudo_legal_moves(board: Board, side: str | None = None) -> list[Move]:
    if side is None:
        side = board.side_to_move

    moves: list[Move] = []
    for index, piece in enumerate(board.squares):
        if piece == EMPTY:
            continue

        if not piece_belongs_to_side(piece, side):
            continue

        moves.extend(generate_piece_moves(board, index))

    return moves

def generate_piece_moves(board: Board, index: int) -> list[Move]:
    piece = board.squares[index]
    if piece == EMPTY:
        return []

    side = WHITE if piece.isupper() else BLACK

    if piece.lower() == "p":
        return generate_pawn_moves(board, index, side)

    if piece.lower() == "n":
        return generate_knight_moves(board, index, side)

    if piece.lower() == "b":
        return generate_sliding_moves(board, index, side, BISHOP_DIRECTIONS)

    if piece.lower() == "r":
        return generate_sliding_moves(board, index, side, ROOK_DIRECTIONS)

    if piece.lower() == "q":
        return generate_sliding_moves(board, index, side, QUEEN_DIRECTIONS)

    if piece.lower() == "k":
        return generate_king_moves(board, index, side)

    return []

def is_square_attacked(board: Board, square: int, by_side: str) -> bool:
    row, col = index_to_row_col(square)

    if by_side == WHITE:
        pawn_sources = [(row + 1, col - 1), (row + 1, col + 1)]
        pawn_piece = "P"
    else:
        pawn_sources = [(row - 1, col -1), (row - 1, col + 1)]
        pawn_piece = "p"

    for r, c in pawn_sources:
        if on_board(r, c) and board.squares[row_col_to_index(r, c)] == pawn_piece:
            return True

    knight_piece = "N" if by_side == WHITE else "n"
    for dr, dc in KNIGHT_DELTAS:
        nr, nc = row + dr, col + dc

        if on_board(nr, nc) and board.squares[row_col_to_index(nr, nc)] == knight_piece:
            return True

    king_piece = "K" if by_side == WHITE else "k"
    for dr, dc in KING_DELTAS:
        nr, nc = row + dr, col + dc

        if on_board(nr, nc) and board.squares[row_col_to_index(nr, nc)] == king_piece:
            return True

    queen_piece = "Q" if by_side == WHITE else "q"

    bishop_piece = "B" if by_side == WHITE else "b"
    for dr, dc in BISHOP_DIRECTIONS:
        nr, nc = row + dr, col + dc

        while on_board(nr, nc):
            piece = board.squares[row_col_to_index(nr, nc)]

            if piece != EMPTY:
                if piece == bishop_piece or piece == queen_piece:
                    return True
                break

            nr += dr
            nc += dc

    rook_piece = "R" if by_side == WHITE else "r"
    for dr, dc in ROOK_DIRECTIONS:
        nr, nc = row + dr, col + dc

        while on_board(nr, nc):
            piece = board.squares[row_col_to_index(nr, nc)]

            if piece != EMPTY:
                if piece == rook_piece or piece == queen_piece:
                    return True
                break

            nr += dr
            nc += dc

    return False


# ----------------------------------------------------
# -- Piece Moves
# ----------------------------------------------------

def generate_pawn_moves(board: Board, index: int, side: str) -> list[Move]:
    moves: list[Move] = []
    row, col = index_to_row_col(index)
    piece = board.squares[index]

    if side == WHITE:
        forward = -1
        start_row = 6
        promotion_row = 0
    else:
        forward = 1
        start_row = 1
        promotion_row = 7

    next_row = row + forward
    if on_board(next_row, col):
        one_step = row_col_to_index(next_row, col)

        if board.squares[one_step] == EMPTY:
            if next_row == promotion_row:
                for promo in ("Q", "R", "B", "N"):
                    promotion_piece = promo if side == WHITE else promo.lower()
                    moves.append(
                        Move(
                            from_square=index,
                            to_square=one_step,
                            piece=piece,
                            captured=EMPTY,
                            promotion=promotion_piece
                        )
                    )
            else:
                moves.append(
                    Move(
                        from_square=index,
                        to_square=one_step,
                        piece=piece,
                        captured=EMPTY
                    )
                )

            if row == start_row:
                two_step_row = row + 2 * forward
                two_step = row_col_to_index(two_step_row, col)

                if board.squares[two_step] == EMPTY:
                    moves.append(
                        Move(
                            from_square=index,
                            to_square=two_step,
                            piece=piece,
                            captured=EMPTY,
                            is_double_pawn_push=True
                        )
                    )

    for dc in (-1, 1):
        capture_col = col + dc
        capture_row = row + forward

        if not on_board(capture_row, capture_col):
            continue

        target = row_col_to_index(capture_row, capture_col)
        target_piece = board.squares[target]

        if piece_belongs_to_enemy(target_piece, side):
            if capture_row == promotion_row:
                for promo in ("Q", "R", "B", "N"):
                    promotion_piece = promo if side == WHITE else promo.lower()
                    moves.append(
                        Move(
                            from_square=index,
                            to_square=target,
                            piece = piece,
                            captured=target_piece,
                            promotion=promotion_piece
                        )
                    )
            else:
                moves.append(
                    Move(
                        from_square=index,
                        to_square=target,
                        piece=piece,
                        captured=target_piece,
                    )
                )

        if board.en_passant is not None and target == board.en_passant:
            captured_piece = "p" if side == WHITE else "P"
            moves.append(
                Move(
                    from_square=index,
                    to_square=target,
                    piece=piece,
                    captured=captured_piece,
                    is_en_passant=True
                )
            )

    return moves

def generate_knight_moves(board: Board, index: int, side: str) -> list[Move]:
    moves: list[Move] = []
    row, col = index_to_row_col(index)
    piece = board.squares[index]

    for dr, dc in KNIGHT_DELTAS:
        nr, nc = row + dr, col + dc

        if not on_board(nr, nc):
            continue

        target = row_col_to_index(nr, nc)
        target_piece = board.squares[target]

        if piece_belongs_to_side(target_piece, side):
            continue

        moves.append(
            Move(
                from_square=index,
                to_square=target,
                piece=piece,
                captured=target_piece,
            )
        )

    return moves

def generate_sliding_moves(
        board: Board,
        index: int,
        side: str,
        directions: Iterable[tuple[int, int]]
) -> list[Move]:
        moves: list[Move] = []
        row, col = index_to_row_col(index)
        piece = board.squares[index]

        for dr, dc in directions:
            nr, nc = row + dr, col + dc

            while on_board(nr, nc):
                target = row_col_to_index(nr, nc)
                target_piece = board.squares[target]

                if target_piece == EMPTY:
                    moves.append(
                        Move(
                            from_square=index,
                            to_square=target,
                            piece=piece,
                            captured=EMPTY
                        )
                    )
                else:
                    if piece_belongs_to_enemy(target_piece, side):
                        moves.append(
                            Move(
                                from_square=index,
                                to_square=target,
                                piece=piece,
                                captured=target_piece
                            )
                        )
                    break

                nr += dr
                nc += dc

        return moves

def generate_king_moves(board: Board, index: int, side: str) -> list[Move]:
    moves: list[Move] = []
    row, col = index_to_row_col(index)
    piece = board.squares[index]

    for dr, dc in KING_DELTAS:
        nr, nc = row + dr, col + dc

        if not on_board(nr, nc):
            continue

        target = row_col_to_index(nr, nc)
        target_piece = board.squares[target]

        if piece_belongs_to_side(target_piece, side):
            continue

        moves.append(
            Move(
                from_square=index,
                to_square=target,
                piece=piece,
                captured=target_piece
            )
        )

    moves.extend(generate_castling_moves(board, side))

    return moves

def generate_castling_moves(board: Board, side: str) -> list[Move]:
    moves: list[Move] = []

    if side == WHITE:
        king_from = square_to_index("e1")

        if board.white_king_pos != king_from:
            return moves

        if is_square_attacked(board, king_from, BLACK):
            return moves

        if "K" in board.castling_rights:
            f1 = square_to_index("f1")
            g1 = square_to_index("g1")
            h1 = square_to_index("h1")

            if (
                board.squares[h1] == "R"
                and board.squares[king_from] == "K"
                and board.squares[f1] == EMPTY
                and board.squares[g1] == EMPTY
                and not is_square_attacked(board, f1, BLACK)
                and not is_square_attacked(board, g1, BLACK)
            ):
                moves.append(
                    Move(
                        from_square=king_from,
                        to_square=g1,
                        piece="K",
                        captured=EMPTY,
                        is_castling=True
                    )
                )

        if "Q" in board.castling_rights:
            d1 = square_to_index("d1")
            c1 = square_to_index("c1")
            b1 = square_to_index("b1")
            a1 = square_to_index("a1")

            if (
                board.squares[a1] == "R"
                and board.squares[king_from] == "K"
                and board.squares[d1] == EMPTY
                and board.squares[c1] == EMPTY
                and board.squares[b1] == EMPTY
                and not is_square_attacked(board, d1, BLACK)
                and not is_square_attacked(board, c1, BLACK)
            ):
                moves.append(
                    Move(
                        from_square=king_from,
                        to_square=c1,
                        piece="K",
                        captured=EMPTY,
                        is_castling=True
                    )
                )
    else:
        king_from = square_to_index("e8")

        if board.black_king_pos != king_from:
            return moves

        if is_square_attacked(board, king_from, WHITE):
            return moves

        if "k" in board.castling_rights:
            f8 = square_to_index("f8")
            g8 = square_to_index("g8")
            h8 = square_to_index("h8")

            if (
                board.squares[h8] == "r"
                and board.squares[king_from] == "k"
                and board.squares[f8] == EMPTY
                and board.squares[g8] == EMPTY
                and not is_square_attacked(board, f8, WHITE)
                and not is_square_attacked(board, g8, WHITE)
            ):
                moves.append(
                    Move(
                        from_square=king_from,
                        to_square=g8,
                        piece="k",
                        captured=EMPTY,
                        is_castling=True
                    )
                )

        if "q" in board.castling_rights:
            d8 = square_to_index("d8")
            c8 = square_to_index("c8")
            b8 = square_to_index("b8")
            a8 = square_to_index("a8")

            if (
                board.squares[a8] == "r"
                and board.squares[king_from] == "k"
                and board.squares[d8] == EMPTY
                and board.squares[c8] == EMPTY
                and board.squares[b8] == EMPTY
                and not is_square_attacked(board, d8, WHITE)
                and not is_square_attacked(board, c8, WHITE)
            ):
                moves.append(
                    Move(
                        from_square=king_from,
                        to_square=c8,
                        piece="k",
                        captured=EMPTY,
                        is_castling=True
                    )
                )

    return moves

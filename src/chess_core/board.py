# chess_core/board.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .constants import (
    BLACK,
    BLACK_PIECES,
    EMPTY,
    START_FEN,
    WHITE,
    WHITE_PIECES
)
from .move import Move, square_to_index, index_to_square
from .zobrist import CASTLING_KEYS, EN_PASSANT_KEYS, PIECE_KEYS, SIDE_TO_MOVE_KEY, hash_position


@dataclass
class BoardState:
    move: Move
    captured_piece: str
    castling_rights: str
    en_passant: Optional[int]
    halfmove_clock: int
    fullmove_number: int
    white_king_pos: int
    black_king_pos: int
    zobrist_key: int


@dataclass
class NullMoveState:
    castling_rights: str
    en_passant: Optional[int]
    halfmove_clock: int
    fullmove_number: int
    side_to_move: str
    zobrist_key: int


def is_white_piece(piece: str) -> bool:
    return piece in WHITE_PIECES


def is_black_piece(piece: str) -> bool:
    return piece in BLACK_PIECES


def same_color(a: str, b: str) -> bool:
    if a == EMPTY or b == EMPTY:
        return False

    return (is_white_piece(a) and is_white_piece(b)) or\
        (is_black_piece(a) and is_black_piece(b))


def enemy_color(piece: str, side: str) -> bool:
    if piece == EMPTY:
        return False

    return (side == WHITE and is_black_piece(piece)) or \
        (side == BLACK and is_white_piece(piece))


class Board:

    def __init__(self, fen: str = START_FEN) -> None:
        self.squares: list[str] = [EMPTY]

        self.side_to_move: str = WHITE
        self.castling_rights: str = "KQkq"
        self.en_passant: Optional[int] = None
        self.halfmove_clock: int = 0
        self.fullmove_number: int = 1

        self.white_king_pos: int = -1
        self.black_king_pos: int = -1

        self.history: list[BoardState] = []
        self.null_history: list[NullMoveState] = []
        self.position_history: list[int] = []
        self.position_counts: dict[int, int] = {}
        self.zobrist_key: int = 0

        self.set_fen(fen)


    # -- Fen --
    def set_fen(self, fen: str) -> None:
        parts = fen.strip().split()
        if len(parts) != 6:
            raise ValueError(f"Invalid FEN: {fen}")

        placement, active, castling, ep, halfmove, fullmove = parts

        self.squares = [EMPTY] * 64
        self.history.clear()
        self.null_history.clear()
        self.position_history.clear()
        self.position_counts.clear()
        self.white_king_pos = -1
        self.black_king_pos = -1

        rows = placement.split("/")
        if len(rows) != 8:
            raise ValueError(f"Invalid FEN rows: {fen}")

        index = 0
        for row in rows:
            for ch in row:
                if ch.isdigit():
                    index += int(ch)
                else:
                    if index >= 64:
                        raise ValueError(f"Invalid FEN placement overflow: {fen}")

                    self.squares[index] = ch
                    if ch == "K":
                        self.white_king_pos = index
                    elif ch == "k":
                        self.black_king_pos = index

                    index += 1

        if index != 64:
            raise ValueError(f"Invalid FEN placement length: {fen}")

        if active not in (WHITE, BLACK):
            raise ValueError(f"Invalid active color: {active}")

        self.side_to_move = active

        self.castling_rights = "" if castling == "-" else castling
        self.en_passant = None if ep == "-" else square_to_index(ep)
        self.halfmove_clock = int(halfmove)
        self.fullmove_number = int(fullmove)

        if self.white_king_pos == -1 or self.black_king_pos == -1:
            raise ValueError("Both kings must exist on board.")

        self.zobrist_key = hash_position(self.squares, self.side_to_move, self.castling_rights, self.en_passant)
        self._record_position(self.zobrist_key)


    def to_fen(self) -> str:
        rows: list[str] = []

        for r in range(8):
            empties = 0
            row_parts: list[str] = []

            for c in range(8):
                piece = self.squares[r * 8 + c]

                if piece == EMPTY:
                    empties += 1
                else:
                    if empties > 0:
                        row_parts.append(str(empties))
                        empties = 0

                    row_parts.append(piece)

            if empties > 0:
                row_parts.append(str(empties))

            rows.append("".join(row_parts))

        placement = "/".join(rows)
        active = self.side_to_move
        castling = self.castling_rights if self.castling_rights else "-"
        ep = "-" if self.en_passant is None else index_to_square(self.en_passant)

        return f"{placement} {active} {castling} {ep} {self.halfmove_clock} {self.fullmove_number}"

    def repetition_count(self) -> int:
        return self.position_counts.get(self.zobrist_key, 0)

    def is_threefold_repetition(self) -> bool:
        return self.repetition_count() >= 3

    def _record_position(self, key: int) -> None:
        self.position_history.append(key)
        self.position_counts[key] = self.position_counts.get(key, 0) + 1

    def _unrecord_position(self) -> None:
        if not self.position_history:
            return
        key = self.position_history.pop()
        count = self.position_counts.get(key, 0)
        if count <= 1:
            self.position_counts.pop(key, None)
        else:
            self.position_counts[key] = count - 1

    def _toggle_piece_hash(self, piece: str, square: int) -> None:
        if piece != EMPTY:
            self.zobrist_key ^= PIECE_KEYS[(piece, square)]

    def _toggle_castling_hash(self, rights: str) -> None:
        for flag in rights:
            self.zobrist_key ^= CASTLING_KEYS[flag]

    def _toggle_en_passant_hash(self, square: Optional[int]) -> None:
        if square is not None:
            self.zobrist_key ^= EN_PASSANT_KEYS[square % 8]

    def _toggle_side_hash(self) -> None:
        self.zobrist_key ^= SIDE_TO_MOVE_KEY


    # -------------------------------------------------
    # -- Square / Piece Helpers
    # -------------------------------------------------
    def piece_at(self, index: int) -> str:
        return self.squares[index]

    def set_piece_at(self, index: int, piece: str) -> None:
        current = self.squares[index]
        if current != EMPTY:
            self._toggle_piece_hash(current, index)
        self.squares[index] = piece
        if piece != EMPTY:
            self._toggle_piece_hash(piece, index)

        if piece == "K":
            self.white_king_pos = index
        elif piece == "k":
            self.black_king_pos = index

    # --------------------------------------------------------
    # -- Move Application
    # --------------------------------------------------------
    @staticmethod
    def _en_passant_capture_square(to_square: int, moving_piece: str) -> int:
        if moving_piece == "P":
            return to_square + 8
        if moving_piece == "p":
            return to_square - 8
        raise ValueError("En passant move must be made by a pawn.")

    def make_move(self, move: Move) -> None:
        moving_piece = self.squares[move.from_square]
        captured_piece = self.squares[move.to_square]

        if moving_piece == EMPTY:
            raise ValueError(f"No piece on from-square: {move}")

        if move.is_en_passant:
            ep_capture_square = self._en_passant_capture_square(move.to_square, moving_piece)
            captured_piece = self.squares[ep_capture_square]

        state = BoardState(
            move=move,
            captured_piece=captured_piece,
            castling_rights=self.castling_rights,
            en_passant=self.en_passant,
            halfmove_clock=self.halfmove_clock,
            fullmove_number=self.fullmove_number,
            white_king_pos=self.white_king_pos,
            black_king_pos=self.black_king_pos,
            zobrist_key=self.zobrist_key,
        )

        self.history.append(state)
        self._toggle_castling_hash(self.castling_rights)
        self._toggle_en_passant_hash(self.en_passant)

        # Reset en passant unless recreated
        self.en_passant = None

        # halfmove clock
        if moving_piece.lower() == "p" or captured_piece != EMPTY:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # handle en passant capture
        if move.is_en_passant:
            ep_capture_square = self._en_passant_capture_square(move.to_square, moving_piece)
            self.squares[ep_capture_square] = EMPTY
            self._toggle_piece_hash(captured_piece, ep_capture_square)

        # move
        self.squares[move.from_square] = EMPTY
        self._toggle_piece_hash(moving_piece, move.from_square)

        placed_piece = move.promotion if move.promotion else moving_piece
        self.squares[move.to_square] = placed_piece
        if captured_piece != EMPTY and not move.is_en_passant:
            self._toggle_piece_hash(captured_piece, move.to_square)
        self._toggle_piece_hash(placed_piece, move.to_square)

        # Update king position
        if moving_piece == "K":
            self.white_king_pos = move.to_square
            self.castling_rights = self.castling_rights.replace("K", "").replace("Q", "")
        elif moving_piece == "k":
            self.black_king_pos = move.to_square
            self.castling_rights = self.castling_rights.replace("k", "").replace("q", "")

        # Remove castling rights if rook moved
        if move.from_square == square_to_index("a1"):
            self.castling_rights = self.castling_rights.replace("Q", "")
        elif move.from_square == square_to_index("h1"):
            self.castling_rights = self.castling_rights.replace("K", "")
        elif move.from_square == square_to_index("a8"):
            self.castling_rights = self.castling_rights.replace("q", "")
        elif move.from_square == square_to_index("h8"):
            self.castling_rights = self.castling_rights.replace("k", "")

        # Remove castling rights if rook captured
        if move.to_square == square_to_index("a1"):
            self.castling_rights = self.castling_rights.replace("Q", "")
        elif move.to_square == square_to_index("h1"):
            self.castling_rights = self.castling_rights.replace("K", "")
        elif move.to_square == square_to_index("a8"):
            self.castling_rights = self.castling_rights.replace("q", "")
        elif move.to_square == square_to_index("h8"):
            self.castling_rights = self.castling_rights.replace("k", "")

        # Handle castling rook move
        if move.is_castling:
            if move.to_square == square_to_index("g1"):
                self.squares[square_to_index("h1")] = EMPTY
                self.squares[square_to_index("f1")] = "R"

            elif move.to_square == square_to_index("c1"):
                self.squares[square_to_index("a1")] = EMPTY
                self.squares[square_to_index("d1")] = "R"

            elif move.to_square == square_to_index("g8"):
                self.squares[square_to_index("h8")] = EMPTY
                self.squares[square_to_index("f8")] = "r"

            elif move.to_square == square_to_index("c8"):
                self.squares[square_to_index("a8")] = EMPTY
                self.squares[square_to_index("d8")] = "r"

        # Create en passant square
        if move.is_double_pawn_push:
            if moving_piece == "P":
                self.en_passant = move.to_square + 8
            elif moving_piece == "p":
                self.en_passant = move.to_square - 8

        # Update move number
        if self.side_to_move == BLACK:
            self.fullmove_number += 1

        # Switch side to move
        self.side_to_move = BLACK if self.side_to_move == WHITE else WHITE
        self._toggle_castling_hash(self.castling_rights)
        self._toggle_en_passant_hash(self.en_passant)
        self._toggle_side_hash()
        self._record_position(self.zobrist_key)


    def undo_move(self) -> None:
        if not self.history:
            return

        self._unrecord_position()
        prev = self.history.pop()
        move = prev.move

        self.side_to_move = WHITE if self.side_to_move == BLACK else BLACK
        self.castling_rights = prev.castling_rights
        self.en_passant = prev.en_passant
        self.halfmove_clock = prev.halfmove_clock
        self.fullmove_number = prev.fullmove_number
        self.white_king_pos = prev.white_king_pos
        self.black_king_pos = prev.black_king_pos
        self.zobrist_key = prev.zobrist_key

        # Clear destination square
        self.squares[move.to_square] = EMPTY

        # Restore moving piece to original square
        self.squares[move.from_square] = move.piece

        # Undo special cases
        if move.is_en_passant:
            # Destination stays empty
            if move.piece == "P":
                self.squares[move.to_square + 8] = "p"
            else:
                self.squares[move.to_square - 8] = "P"

        elif move.is_castling:
            # Restore captured piece at destination
            self.squares[move.to_square] = prev.captured_piece

            if move.to_square == square_to_index("g1"):
                self.squares[square_to_index("f1")] = EMPTY
                self.squares[square_to_index("h1")] = "R"
            elif move.to_square == square_to_index("c1"):
                self.squares[square_to_index("d1")] = EMPTY
                self.squares[square_to_index("a1")] = "R"
            elif move.to_square == square_to_index("g8"):
                self.squares[square_to_index("f8")] = EMPTY
                self.squares[square_to_index("h8")] = "r"
            elif move.to_square == square_to_index("c8"):
                self.squares[square_to_index("d8")] = EMPTY
                self.squares[square_to_index("a8")] = "r"

        else:
            # Normal move or promotion
            self.squares[move.to_square] = prev.captured_piece

    def make_null_move(self) -> None:
        state = NullMoveState(
            castling_rights=self.castling_rights,
            en_passant=self.en_passant,
            halfmove_clock=self.halfmove_clock,
            fullmove_number=self.fullmove_number,
            side_to_move=self.side_to_move,
            zobrist_key=self.zobrist_key,
        )
        self.null_history.append(state)
        self._toggle_en_passant_hash(self.en_passant)
        self.en_passant = None
        self.halfmove_clock += 1
        if self.side_to_move == BLACK:
            self.fullmove_number += 1
        self.side_to_move = BLACK if self.side_to_move == WHITE else WHITE
        self._toggle_side_hash()
        self._record_position(self.zobrist_key)

    def undo_null_move(self) -> None:
        if not self.null_history:
            return
        self._unrecord_position()
        prev = self.null_history.pop()
        self.castling_rights = prev.castling_rights
        self.en_passant = prev.en_passant
        self.halfmove_clock = prev.halfmove_clock
        self.fullmove_number = prev.fullmove_number
        self.side_to_move = prev.side_to_move
        self.zobrist_key = prev.zobrist_key


    # ---------------------------------------
    # -- Debug
    # ---------------------------------------

    def print_board(self) -> None:
        for r in range(8):
            row = self.squares[r * 8: (r + 1) * 8]
            print(8 - r, " ".join(row))

        print("  a b c d e f g h")
        print(
            f"Turn: {self.side_to_move}, Castling: {self.castling_rights or '-'}, "
            f"EP: {index_to_square(self.en_passant) if self.en_passant is not None else '-'}"
        )
        print()

    def __str__(self) -> str:
        rows = []
        for r in range(8):
            row = self.squares[r * 8: (r + 1) * 8]
            rows.append(" ".join(row))

        return "\n".join(rows)

# chess_core/move.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .constants import FILES


def index_to_square(index: int) -> str:
    row = index // 8
    col = index % 8
    file_char = FILES[col]
    rank_char = str(8 - row)

    return f"{file_char}{rank_char}"


def square_to_index(square: str) -> int:
    if len(square) != 2:
        raise ValueError(f"Invalid square: {square}")

    file_char, rank_char = square[0], square[1]
    if file_char not in FILES or rank_char not in "12345678":
        raise ValueError(f"Invalid square: {square}")

    col = FILES.index(file_char)
    row = 8 - int(rank_char)

    return row * 8 + col


@dataclass
class Move:
    from_square: int
    to_square: int
    piece: str
    captured: str = "."
    promotion: Optional[str] = None

    is_en_passant: bool = False
    is_castling: bool = False
    is_double_pawn_push: bool = False


    def uci(self) -> str:
        move_str = f"{index_to_square(self.from_square)}{index_to_square(self.to_square)}"
        if self.promotion:
            move_str += self.promotion.lower()

        return move_str


    def __str__(self) -> str:
        return self.uci()

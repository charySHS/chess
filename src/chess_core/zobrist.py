from __future__ import annotations

from random import Random

from src.chess_core.constants import BLACK, PIECE_TYPES


_RNG = Random(1337)
_PIECES = sorted(PIECE_TYPES)
_CASTLING_MASKS = ("K", "Q", "k", "q")

PIECE_KEYS: dict[tuple[str, int], int] = {
    (piece, square): _RNG.getrandbits(64)
    for piece in _PIECES
    for square in range(64)
}
CASTLING_KEYS: dict[str, int] = {flag: _RNG.getrandbits(64) for flag in _CASTLING_MASKS}
EN_PASSANT_KEYS: dict[int, int] = {file_index: _RNG.getrandbits(64) for file_index in range(8)}
SIDE_TO_MOVE_KEY = _RNG.getrandbits(64)


def hash_position(
    squares: list[str],
    side_to_move: str,
    castling_rights: str,
    en_passant: int | None,
) -> int:
    key = 0
    for square, piece in enumerate(squares):
        if piece != ".":
            key ^= PIECE_KEYS[(piece, square)]
    for flag in castling_rights:
        key ^= CASTLING_KEYS[flag]
    if en_passant is not None:
        key ^= EN_PASSANT_KEYS[en_passant % 8]
    if side_to_move == BLACK:
        key ^= SIDE_TO_MOVE_KEY
    return key

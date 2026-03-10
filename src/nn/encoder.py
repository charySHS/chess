from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    np = None

from src.chess_core.constants import BLACK, WHITE

if TYPE_CHECKING:
    from src.chess_core import Board

PIECE_ORDER = "PNBRQKpnbrqk"
ENCODED_SIZE = len(PIECE_ORDER) * 64 + 1 + 4 + 64


def require_numpy() -> None:
    if np is None:
        raise RuntimeError("numpy is required for NN encoding and training.")


def encode_board(board: Board):
    require_numpy()
    features = np.zeros(ENCODED_SIZE, dtype=np.float32)

    for square, piece in enumerate(board.squares):
        if piece == ".":
            continue
        plane = PIECE_ORDER.index(piece)
        features[plane * 64 + square] = 1.0

    offset = len(PIECE_ORDER) * 64
    features[offset] = 1.0 if board.side_to_move == WHITE else 0.0
    features[offset + 1] = 1.0 if "K" in board.castling_rights else 0.0
    features[offset + 2] = 1.0 if "Q" in board.castling_rights else 0.0
    features[offset + 3] = 1.0 if "k" in board.castling_rights else 0.0
    features[offset + 4] = 1.0 if "q" in board.castling_rights else 0.0
    if board.en_passant is not None:
        features[offset + 5 + board.en_passant] = 1.0
    return features


def normalize_centipawns(score_cp: int) -> float:
    require_numpy()
    return float(np.tanh(score_cp / 400.0))


def denormalize_value(value: float) -> float:
    require_numpy()
    clipped = float(np.clip(value, -0.999, 0.999))
    return float(np.arctanh(clipped) * 400.0)

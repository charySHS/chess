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
GLOBAL_FEATURES = 2 + 4 + 64 + len(PIECE_ORDER) + 3
ENCODED_SIZE = len(PIECE_ORDER) * 64 + GLOBAL_FEATURES

SIDE_TO_MOVE_OFFSET = len(PIECE_ORDER) * 64
CASTLING_OFFSET = SIDE_TO_MOVE_OFFSET + 2
EN_PASSANT_OFFSET = CASTLING_OFFSET + 4
COUNT_OFFSET = EN_PASSANT_OFFSET + 64
MATERIAL_OFFSET = COUNT_OFFSET + len(PIECE_ORDER)


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

    features[SIDE_TO_MOVE_OFFSET] = 1.0 if board.side_to_move == WHITE else 0.0
    features[SIDE_TO_MOVE_OFFSET + 1] = 1.0 if board.side_to_move == BLACK else 0.0
    features[CASTLING_OFFSET] = 1.0 if "K" in board.castling_rights else 0.0
    features[CASTLING_OFFSET + 1] = 1.0 if "Q" in board.castling_rights else 0.0
    features[CASTLING_OFFSET + 2] = 1.0 if "k" in board.castling_rights else 0.0
    features[CASTLING_OFFSET + 3] = 1.0 if "q" in board.castling_rights else 0.0
    if board.en_passant is not None:
        features[EN_PASSANT_OFFSET + board.en_passant] = 1.0

    for piece in PIECE_ORDER:
        features[COUNT_OFFSET + PIECE_ORDER.index(piece)] = sum(1 for current in board.squares if current == piece) / 8.0

    white_material = 0.0
    black_material = 0.0
    for piece in board.squares:
        if piece == "." or piece.lower() == "k":
            continue
        value = {
            "p": 1.0,
            "n": 3.0,
            "b": 3.0,
            "r": 5.0,
            "q": 9.0,
        }.get(piece.lower(), 0.0)
        if piece.isupper():
            white_material += value
        else:
            black_material += value
    features[MATERIAL_OFFSET] = white_material / 39.0
    features[MATERIAL_OFFSET + 1] = black_material / 39.0
    features[MATERIAL_OFFSET + 2] = (white_material - black_material) / 39.0
    return features


def mirror_encoded_features(features):
    require_numpy()
    mirrored = np.zeros_like(features)

    for plane in range(len(PIECE_ORDER)):
        start = plane * 64
        mirrored_plane = features[start : start + 64].reshape(8, 8)[:, ::-1]
        mirrored[start : start + 64] = mirrored_plane.reshape(64)

    mirrored[SIDE_TO_MOVE_OFFSET : SIDE_TO_MOVE_OFFSET + 2] = features[SIDE_TO_MOVE_OFFSET : SIDE_TO_MOVE_OFFSET + 2]
    mirrored[CASTLING_OFFSET] = features[CASTLING_OFFSET + 1]
    mirrored[CASTLING_OFFSET + 1] = features[CASTLING_OFFSET]
    mirrored[CASTLING_OFFSET + 2] = features[CASTLING_OFFSET + 3]
    mirrored[CASTLING_OFFSET + 3] = features[CASTLING_OFFSET + 2]

    en_passant = features[EN_PASSANT_OFFSET : EN_PASSANT_OFFSET + 64].reshape(8, 8)[:, ::-1]
    mirrored[EN_PASSANT_OFFSET : EN_PASSANT_OFFSET + 64] = en_passant.reshape(64)
    mirrored[COUNT_OFFSET : COUNT_OFFSET + len(PIECE_ORDER)] = features[COUNT_OFFSET : COUNT_OFFSET + len(PIECE_ORDER)]
    mirrored[MATERIAL_OFFSET : MATERIAL_OFFSET + 3] = features[MATERIAL_OFFSET : MATERIAL_OFFSET + 3]
    return mirrored


def normalize_centipawns(score_cp: int) -> float:
    require_numpy()
    return float(np.tanh(score_cp / 400.0))


def denormalize_value(value: float) -> float:
    require_numpy()
    clipped = float(np.clip(value, -0.999, 0.999))
    return float(np.arctanh(clipped) * 400.0)

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from src.chess_core import Board, Move, generate_legal_moves
from src.engine.stockfish_bridge import MoveReview, StockfishBridge
from src.nn.encoder import encode_board, mirror_encoded_features, normalize_centipawns, require_numpy

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    np = None


@dataclass(frozen=True)
class TrainingSample:
    fen: str
    value_cp: int
    best_move: str | None = None
    played_move: str | None = None
    review_label: str | None = None
    loss_cp: int | None = None


def append_samples(path: Path, samples: Iterable[TrainingSample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for sample in samples:
            handle.write(json.dumps(asdict(sample)) + "\n")


def load_samples(path: Path) -> list[TrainingSample]:
    if not path.exists():
        return []
    samples: list[TrainingSample] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            samples.append(TrainingSample(**payload))
    return samples


def samples_to_arrays(samples: list[TrainingSample]):
    require_numpy()
    x = np.stack([encode_board(Board(sample.fen)) for sample in samples])
    y = np.asarray([normalize_centipawns(sample.value_cp) for sample in samples], dtype=np.float32).reshape(-1, 1)
    return x, y


def augment_with_mirrors(x, y):
    require_numpy()
    mirrored = np.stack([mirror_encoded_features(features) for features in x])
    x_augmented = np.concatenate((x, mirrored), axis=0)
    y_augmented = np.concatenate((y, y.copy()), axis=0)
    return x_augmented, y_augmented


def generate_stockfish_samples(
    bridge: StockfishBridge,
    fens: Iterable[str],
    depth: int = 12,
    include_move_review: bool = False,
) -> list[TrainingSample]:
    samples: list[TrainingSample] = []
    for fen in fens:
        analysis = bridge.analyse_fen(fen, depth=depth, multipv=1)
        best_line = analysis.best_line
        if best_line is None:
            continue
        sample = TrainingSample(
            fen=fen,
            value_cp=best_line.score.as_centipawns(),
            best_move=best_line.pv[0] if best_line.pv else None,
        )
        samples.append(sample)

        if include_move_review:
            board = Board(fen)
            legal_moves = generate_legal_moves(board)
            if legal_moves:
                review = bridge.review_move(board, legal_moves[0], depth=depth)
                reviewed = TrainingSample(
                    fen=fen,
                    value_cp=best_line.score.as_centipawns(),
                    best_move=review.best_move,
                    played_move=review.played_move,
                    review_label=review.label,
                    loss_cp=review.loss_cp,
                )
                samples.append(reviewed)
    return samples

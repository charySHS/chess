from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.chess_core import Board, Move, generate_legal_moves
from src.nn.encoder import encode_board, denormalize_value
from src.nn.model import ValueNetwork


@dataclass(frozen=True)
class MoveScore:
    move: Move
    value: float


class NeuralEvaluator:
    def __init__(self, model: ValueNetwork) -> None:
        self.model = model

    @classmethod
    def from_path(cls, path: Path) -> NeuralEvaluator:
        return cls(ValueNetwork.load(path))

    def evaluate_board(self, board: Board) -> float:
        features = self._adapt_features(encode_board(board)).reshape(1, -1)
        prediction = float(self.model.predict(features)[0, 0])
        return denormalize_value(prediction)

    def rank_moves(self, board: Board) -> list[MoveScore]:
        scored: list[MoveScore] = []
        for move in generate_legal_moves(board):
            child = Board(board.to_fen())
            child.make_move(move)
            score = -self.evaluate_board(child)
            scored.append(MoveScore(move=move, value=score))
        return sorted(scored, key=lambda item: item.value, reverse=True)

    def _adapt_features(self, features):
        input_size = self.model.config.input_size
        if features.shape[0] == input_size:
            return features
        if features.shape[0] > input_size:
            return features[:input_size]

        padded = features.copy()
        extra = input_size - features.shape[0]
        if extra > 0:
            import numpy as np

            padded = np.pad(padded, (0, extra))
        return padded

from __future__ import annotations

from dataclasses import dataclass

from src.chess_core import Board
from src.chess_core.constants import PIECE_VALUES
from src.nn.infer import NeuralEvaluator


@dataclass
class HybridEvaluator:
    neural: NeuralEvaluator | None = None
    material_weight: float = 1.0
    neural_weight: float = 1.0

    def evaluate(self, board: Board) -> float:
        material = sum(PIECE_VALUES.get(piece, 0) for piece in board.squares)
        score = self.material_weight * material
        if self.neural is not None:
            score += self.neural_weight * self.neural.evaluate_board(board)
        return float(score)

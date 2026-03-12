from __future__ import annotations

from dataclasses import dataclass

from src.chess_core import Board
from src.chess_core.constants import PIECE_VALUES
from src.chess_core.movegen import generate_pseudo_legal_moves, is_in_check
from src.engine.profile import EvaluatorConfig
from src.nn.infer import NeuralEvaluator

PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    6, 8, 10, 16, 16, 10, 8, 6,
    5, 6, 8, 14, 14, 8, 6, 5,
    4, 5, 7, 12, 12, 7, 5, 4,
    3, 4, 6, 10, 10, 6, 4, 3,
    2, 3, 4, 6, 6, 4, 3, 2,
    4, 4, 4, -6, -6, 4, 4, 4,
    0, 0, 0, 0, 0, 0, 0, 0,
]

KNIGHT_TABLE = [
    -18, -10, -6, -6, -6, -6, -10, -18,
    -10, -2, 2, 3, 3, 2, -2, -10,
    -6, 3, 8, 10, 10, 8, 3, -6,
    -6, 5, 10, 12, 12, 10, 5, -6,
    -6, 5, 10, 12, 12, 10, 5, -6,
    -6, 3, 8, 10, 10, 8, 3, -6,
    -10, -2, 2, 5, 5, 2, -2, -10,
    -18, -10, -6, -6, -6, -6, -10, -18,
]

BISHOP_TABLE = [
    -8, -4, -3, -3, -3, -3, -4, -8,
    -4, 2, 2, 2, 2, 2, 2, -4,
    -3, 2, 4, 6, 6, 4, 2, -3,
    -3, 3, 6, 8, 8, 6, 3, -3,
    -3, 3, 6, 8, 8, 6, 3, -3,
    -3, 2, 4, 6, 6, 4, 2, -3,
    -4, 1, 2, 2, 2, 2, 1, -4,
    -8, -4, -3, -3, -3, -3, -4, -8,
]

ROOK_TABLE = [
    4, 6, 8, 10, 10, 8, 6, 4,
    4, 6, 8, 10, 10, 8, 6, 4,
    0, 2, 4, 8, 8, 4, 2, 0,
    -2, 0, 2, 6, 6, 2, 0, -2,
    -2, 0, 2, 6, 6, 2, 0, -2,
    -2, 0, 2, 6, 6, 2, 0, -2,
    -2, 0, 2, 6, 6, 2, 0, -2,
    0, 2, 6, 8, 8, 6, 2, 0,
]

QUEEN_TABLE = [
    -8, -4, -2, 0, 0, -2, -4, -8,
    -4, 0, 2, 2, 2, 2, 0, -4,
    -2, 2, 4, 4, 4, 4, 2, -2,
    0, 2, 4, 5, 5, 4, 2, 0,
    0, 2, 4, 5, 5, 4, 2, 0,
    -2, 2, 4, 4, 4, 4, 2, -2,
    -4, 0, 2, 2, 2, 2, 0, -4,
    -8, -4, -2, 0, 0, -2, -4, -8,
]

KING_TABLE = [
    -18, -20, -20, -22, -22, -20, -20, -18,
    -16, -18, -18, -20, -20, -18, -18, -16,
    -12, -14, -16, -18, -18, -16, -14, -12,
    -8, -10, -14, -16, -16, -14, -10, -8,
    -4, -8, -12, -14, -14, -12, -8, -4,
    2, -4, -8, -10, -10, -8, -4, 2,
    10, 8, 2, -4, -4, 2, 8, 10,
    14, 16, 8, 0, 0, 8, 16, 14,
]

PIECE_SQUARE_TABLES = {
    "P": PAWN_TABLE,
    "N": KNIGHT_TABLE,
    "B": BISHOP_TABLE,
    "R": ROOK_TABLE,
    "Q": QUEEN_TABLE,
    "K": KING_TABLE,
}


@dataclass
class HybridEvaluator:
    neural: NeuralEvaluator | None = None
    material_weight: float = 1.0
    neural_weight: float = 1.0
    mobility_weight: float = 0.35
    passed_pawn_weight: float = 1.0
    rook_file_weight: float = 1.0
    king_safety_weight: float = 1.0
    endgame_king_weight: float = 1.0

    @classmethod
    def from_config(cls, config: EvaluatorConfig, neural: NeuralEvaluator | None = None) -> HybridEvaluator:
        return cls(
            neural=neural,
            material_weight=config.material_weight,
            neural_weight=config.neural_weight,
            mobility_weight=config.mobility_weight,
            passed_pawn_weight=config.passed_pawn_weight,
            rook_file_weight=config.rook_file_weight,
            king_safety_weight=config.king_safety_weight,
            endgame_king_weight=config.endgame_king_weight,
        )

    def evaluate(self, board: Board) -> float:
        material = 0.0
        placement = 0.0
        white_bishops = 0
        black_bishops = 0
        white_material = 0.0
        black_material = 0.0

        for square, piece in enumerate(board.squares):
            if piece == ".":
                continue

            material += PIECE_VALUES.get(piece, 0)
            placement += self._piece_square_bonus(piece, square)
            if piece == "B":
                white_bishops += 1
                white_material += 300
            elif piece == "b":
                black_bishops += 1
                black_material += 300
            elif piece.isupper():
                white_material += abs(PIECE_VALUES.get(piece, 0))
            else:
                black_material += abs(PIECE_VALUES.get(piece, 0))

        score = self.material_weight * material
        score += placement
        score += self._center_control_bonus(board)
        score += self._pawn_structure_bonus(board)
        score += self.king_safety_weight * self._king_safety_bonus(board)
        score += self.mobility_weight * self._mobility_bonus(board)
        score += self.passed_pawn_weight * self._passed_pawn_bonus(board)
        score += self.rook_file_weight * self._rook_file_bonus(board)
        score += self.endgame_king_weight * self._endgame_king_activity_bonus(board, white_material, black_material)
        if white_bishops >= 2:
            score += 24
        if black_bishops >= 2:
            score -= 24

        if self.neural is not None:
            score += self.neural_weight * self.neural.evaluate_board(board)
        return float(score)

    def _piece_square_bonus(self, piece: str, square: int) -> float:
        table = PIECE_SQUARE_TABLES.get(piece.upper())
        if table is None:
            return 0.0

        index = square if piece.isupper() else 63 - square
        value = table[index]
        return float(value if piece.isupper() else -value)

    def _center_control_bonus(self, board: Board) -> float:
        center_squares = (27, 28, 35, 36)
        score = 0.0
        for square in center_squares:
            piece = board.squares[square]
            if piece == ".":
                continue
            score += 12.0 if piece.isupper() else -12.0
        return score

    def _pawn_structure_bonus(self, board: Board) -> float:
        white_files = [0] * 8
        black_files = [0] * 8
        for square, piece in enumerate(board.squares):
            if piece == "P":
                white_files[square % 8] += 1
            elif piece == "p":
                black_files[square % 8] += 1

        score = 0.0
        for file_index in range(8):
            if white_files[file_index] > 1:
                score -= 14.0 * (white_files[file_index] - 1)
            if black_files[file_index] > 1:
                score += 14.0 * (black_files[file_index] - 1)

            if white_files[file_index] > 0:
                left = white_files[file_index - 1] if file_index > 0 else 0
                right = white_files[file_index + 1] if file_index < 7 else 0
                if left == 0 and right == 0:
                    score -= 10.0

            if black_files[file_index] > 0:
                left = black_files[file_index - 1] if file_index > 0 else 0
                right = black_files[file_index + 1] if file_index < 7 else 0
                if left == 0 and right == 0:
                    score += 10.0
        return score

    def _king_safety_bonus(self, board: Board) -> float:
        score = 0.0
        white_rank = board.white_king_pos // 8
        black_rank = board.black_king_pos // 8
        if white_rank >= 6:
            score += 16.0
        if black_rank <= 1:
            score -= 16.0
        if is_in_check(board, "w"):
            score -= 20.0
        if is_in_check(board, "b"):
            score += 20.0
        return score

    def _mobility_bonus(self, board: Board) -> float:
        white_moves = len(generate_pseudo_legal_moves(board, "w"))
        black_moves = len(generate_pseudo_legal_moves(board, "b"))
        return float((white_moves - black_moves) * 1.6)

    def _passed_pawn_bonus(self, board: Board) -> float:
        score = 0.0
        for square, piece in enumerate(board.squares):
            if piece not in ("P", "p"):
                continue
            row = square // 8
            file_index = square % 8
            adjacent_files = range(max(0, file_index - 1), min(7, file_index + 1) + 1)
            blocked = False
            if piece == "P":
                for check_row in range(0, row):
                    for check_file in adjacent_files:
                        if board.squares[check_row * 8 + check_file] == "p":
                            blocked = True
                            break
                    if blocked:
                        break
                if not blocked:
                    score += 18.0 + (6 - row) * 8.0
            else:
                for check_row in range(row + 1, 8):
                    for check_file in adjacent_files:
                        if board.squares[check_row * 8 + check_file] == "P":
                            blocked = True
                            break
                    if blocked:
                        break
                if not blocked:
                    score -= 18.0 + (row - 1) * 8.0
        return score

    def _rook_file_bonus(self, board: Board) -> float:
        score = 0.0
        for square, piece in enumerate(board.squares):
            if piece not in ("R", "r"):
                continue
            file_index = square % 8
            white_pawn = False
            black_pawn = False
            for rank in range(8):
                occupant = board.squares[rank * 8 + file_index]
                if occupant == "P":
                    white_pawn = True
                elif occupant == "p":
                    black_pawn = True
            if piece == "R":
                if not white_pawn and not black_pawn:
                    score += 24.0
                elif not white_pawn:
                    score += 12.0
            else:
                if not white_pawn and not black_pawn:
                    score -= 24.0
                elif not black_pawn:
                    score -= 12.0
        return score

    def _endgame_king_activity_bonus(self, board: Board, white_material: float, black_material: float) -> float:
        heavy_material = white_material + black_material
        if heavy_material > 2600:
            return 0.0

        white_row, white_col = divmod(board.white_king_pos, 8)
        black_row, black_col = divmod(board.black_king_pos, 8)
        white_center_distance = abs(white_row - 3.5) + abs(white_col - 3.5)
        black_center_distance = abs(black_row - 3.5) + abs(black_col - 3.5)
        return (black_center_distance - white_center_distance) * 8.0

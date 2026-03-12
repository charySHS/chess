from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from shutil import which

from src.chess_core import Board, Move, START_FEN, generate_legal_moves, is_checkmate, is_in_check, is_stalemate
from src.chess_core.constants import BLACK, EMPTY, WHITE
from src.config import AppConfig
from src.engine.profile import load_latest_engine_profile
from src.engine.search import SearchEngine, SearchResult
from src.engine.stockfish_bridge import MoveReview, Score, StockfishBridge, classify_move_loss

MATE_SCORE_CP = 100000


PIECE_TO_GLYPH = {
    "K": "♔",
    "Q": "♕",
    "R": "♖",
    "B": "♗",
    "N": "♘",
    "P": "♙",
    "k": "♚",
    "q": "♛",
    "r": "♜",
    "b": "♝",
    "n": "♞",
    "p": "♟",
}


@dataclass(frozen=True)
class GameResult:
    is_over: bool
    headline: str
    winner: str | None = None
    reason: str | None = None


@dataclass
class PendingPromotion:
    moves: list[Move]


class GameController:
    def __init__(self) -> None:
        self.board = Board(START_FEN)
        self.flipped = False
        self.mode = "local"
        self.human_side = WHITE
        self.selected_square: int | None = None
        self.legal_moves: list[Move] = []
        self.legal_moves_by_from: dict[int, list[Move]] = {}
        self.result = GameResult(False, "In Progress")
        self.pending_promotion: PendingPromotion | None = None
        self.move_scroll_offset = 0
        latest = load_latest_engine_profile(Path("artifacts/engine_snapshots"))
        self.engine = SearchEngine(profile=latest[0]) if latest is not None else SearchEngine()
        self.engine_snapshot: SearchResult | None = None
        self.last_review: MoveReview | None = None
        self.refresh_legal_moves()

    def configure_mode(self, mode: str) -> None:
        self.mode = mode
        self.human_side = WHITE
        self.reset_board()

    def reset_board(self) -> None:
        self.board = Board(START_FEN)
        self.selected_square = None
        self.pending_promotion = None
        self.move_scroll_offset = 0
        self.last_review = None
        self.refresh_legal_moves()

    def undo_last_move(self) -> None:
        if not self.board.history:
            return
        self.board.undo_move()
        self.selected_square = None
        self.pending_promotion = None
        self.last_review = None
        self.refresh_legal_moves()

    def toggle_flip(self) -> None:
        self.flipped = not self.flipped

    def refresh_legal_moves(self) -> None:
        self.legal_moves = generate_legal_moves(self.board)
        grouped: dict[int, list[Move]] = {}
        for move in self.legal_moves:
            grouped.setdefault(move.from_square, []).append(move)
        self.legal_moves_by_from = grouped
        self.result = self.evaluate_result()
        self._refresh_engine_snapshot()

    def piece_at(self, square: int) -> str:
        return self.board.piece_at(square)

    def glyph_at(self, square: int) -> str:
        return PIECE_TO_GLYPH.get(self.piece_at(square), "")

    def display_squares(self) -> list[int]:
        ordered: list[int] = []
        for display_row in range(8):
            for display_col in range(8):
                board_row = 7 - display_row if self.flipped else display_row
                board_col = 7 - display_col if self.flipped else display_col
                ordered.append(board_row * 8 + board_col)
        return ordered

    def select_or_move(self, square: int) -> bool:
        if not self.interaction_allowed():
            return False

        if self.selected_square is not None:
            matching_moves = [move for move in self.legal_moves_by_from.get(self.selected_square, []) if move.to_square == square]
            if matching_moves and square != self.selected_square:
                return self._resolve_moves(matching_moves)

        piece = self.board.piece_at(square)
        legal_moves = self.legal_moves_for_square(square)
        if piece == EMPTY or not legal_moves:
            self.selected_square = None
            return False

        self.selected_square = square
        return False

    def choose_promotion(self, promotion_code: str) -> bool:
        if self.pending_promotion is None:
            return False
        for move in self.pending_promotion.moves:
            if move.promotion is not None and move.promotion.upper() == promotion_code:
                self.apply_move(move)
                self.selected_square = None
                return True
        return False

    def legal_moves_for_square(self, square: int) -> list[Move]:
        piece = self.board.piece_at(square)
        if not self._piece_belongs_to_side_to_move(piece):
            return []
        return list(self.legal_moves_by_from.get(square, []))

    def legal_targets(self) -> set[int]:
        if self.selected_square is None:
            return set()
        return {move.to_square for move in self.legal_moves_by_from.get(self.selected_square, [])}

    def apply_move(self, move: Move) -> None:
        board_before = Board(self.board.to_fen())
        self.board.make_move(move)
        self.pending_promotion = None
        self.selected_square = None
        self.last_review = self._review_move(board_before, move)
        self.refresh_legal_moves()

    def maybe_make_engine_move(self) -> bool:
        if self.mode != "engine":
            return False
        if self.pending_promotion is not None or self.result.is_over:
            return False
        if self.board.side_to_move == self.human_side:
            return False
        engine_move = self.engine.choose_move(self.board, depth=2)
        if engine_move is None:
            return False
        self.apply_move(engine_move)
        return True

    def interaction_allowed(self) -> bool:
        return (
            not self.result.is_over
            and self.pending_promotion is None
            and (self.mode != "engine" or self.board.side_to_move == self.human_side)
        )

    def status_text(self) -> str:
        side = "White" if self.board.side_to_move == WHITE else "Black"
        mode_label = "Engine" if self.mode == "engine" else "Local"
        tags: list[str] = [f"Turn: {side}", f"Mode: {mode_label}"]
        if self.result.is_over:
            tags.append(self.result.headline)
        elif self.pending_promotion is not None:
            tags.append("Choose promotion")
        elif is_in_check(self.board):
            tags.append("Check")
        return "  |  ".join(tags)

    def detail_lines(self) -> list[str]:
        side = "White" if self.board.side_to_move == WHITE else "Black"
        lines = [
            f"Mode: {'Human vs Engine' if self.mode == 'engine' else 'Local pass-and-play'}",
            f"Side to move: {side}",
            f"Moves available: {len(self.legal_moves)}",
            f"Last move: {self.last_move().uci() if self.last_move() else '--'}",
        ]
        if self.result.is_over:
            lines.append(f"Result: {self.result.headline}")
        elif self.pending_promotion is not None:
            lines.append("Promotion pending")
        elif is_in_check(self.board):
            lines.append(f"{side} is in check")
        return lines

    def engine_lines(self) -> list[str]:
        if self.engine_snapshot is None or self.engine_snapshot.best_move is None:
            return ["Engine: waiting", "Best move: --", "Eval: --", "Depth: --"]
        return [
            f"Engine: {'active' if self.mode == 'engine' else 'analysis'}",
            f"Best move: {self.engine_snapshot.best_move.uci()}",
            f"Eval: {self.engine_snapshot.score:.1f}",
            f"Depth {self.engine_snapshot.depth}  Nodes {self.engine_snapshot.nodes}",
        ]

    def captures_text(self) -> str:
        captured_by_white, captured_by_black = self.captured_pieces()
        white = " ".join(PIECE_TO_GLYPH[piece] for piece in captured_by_white) or "None"
        black = " ".join(PIECE_TO_GLYPH[piece] for piece in captured_by_black) or "None"
        return f"White: {white}\nBlack: {black}"

    def review_text(self) -> str:
        if self.last_review is None:
            return "Review: --"
        best = self.last_review.best_move or "--"
        return f"Review: {self.last_review.label.title()}\nBest line move: {best}"

    def move_rows(self) -> list[str]:
        rows: list[str] = []
        history = self.board.history
        for index in range(0, len(history), 2):
            move_number = index // 2 + 1
            white_move = history[index].move.uci()
            black_move = history[index + 1].move.uci() if index + 1 < len(history) else ""
            rows.append(f"{move_number}. {white_move} {black_move}".rstrip())
        return rows

    def captured_pieces(self) -> tuple[list[str], list[str]]:
        captured_by_white: list[str] = []
        captured_by_black: list[str] = []
        for state in self.board.history:
            if state.captured_piece == EMPTY:
                continue
            if state.captured_piece.islower():
                captured_by_white.append(state.captured_piece)
            else:
                captured_by_black.append(state.captured_piece)
        return captured_by_white, captured_by_black

    def last_move(self) -> Move | None:
        if not self.board.history:
            return None
        return self.board.history[-1].move

    def evaluate_result(self) -> GameResult:
        if is_checkmate(self.board):
            winner = "Black" if self.board.side_to_move == WHITE else "White"
            return GameResult(True, f"Checkmate: {winner} wins", winner=winner, reason="checkmate")
        if is_stalemate(self.board):
            return GameResult(True, "Draw by stalemate", reason="stalemate")
        return GameResult(False, "In Progress")

    def _resolve_moves(self, moves: list[Move]) -> bool:
        if not moves:
            return False
        if len(moves) > 1 and all(move.promotion is not None for move in moves):
            ordered = sorted(moves, key=lambda move: "QRBN".index(move.promotion.upper()))
            self.pending_promotion = PendingPromotion(ordered)
            return True
        self.apply_move(moves[0])
        return True

    def _refresh_engine_snapshot(self) -> None:
        if self.result.is_over or not self.legal_moves:
            self.engine_snapshot = None
            return
        self.engine_snapshot = self.engine.iterative_deepening(self.board, max_depth=2)

    def _review_move(self, board_before: Board, move: Move) -> MoveReview | None:
        config = AppConfig()
        review_depth = max(10, config.stockfish_depth)
        fallback_depth = 3
        stockfish_path = config.stockfish_path
        if which(stockfish_path) or Path(stockfish_path).exists():
            try:
                with StockfishBridge(path=stockfish_path) as bridge:
                    return bridge.review_move(board_before, move, depth=review_depth)
            except Exception:
                pass

        best_result = self.engine.iterative_deepening(board_before, max_depth=fallback_depth)
        child_board = Board(board_before.to_fen())
        child_board.make_move(move)
        played_result = self.engine.iterative_deepening(child_board, max_depth=max(2, fallback_depth - 1))
        best_score = self._normalize_review_score(best_result.score if best_result.best_move is not None else 0.0)
        played_score = self._normalize_review_score(-played_result.score)
        loss_cp = max(0, best_score - played_score)
        best_move = best_result.best_move.uci() if best_result.best_move is not None else None
        best_margin_cp = self._fallback_best_margin(board_before, best_move)
        return MoveReview(
            played_move=move.uci(),
            best_move=best_move,
            played_score=Score(cp=played_score),
            best_score=Score(cp=best_score),
            loss_cp=loss_cp,
            label=classify_move_loss(loss_cp, move.uci(), best_move, best_margin_cp=best_margin_cp),
        )

    def _normalize_review_score(self, score: float) -> int:
        if not isfinite(score):
            return MATE_SCORE_CP if score > 0 else -MATE_SCORE_CP
        return int(max(-MATE_SCORE_CP, min(MATE_SCORE_CP, score)))

    def _fallback_best_margin(self, board_before: Board, best_move: str | None) -> int | None:
        if best_move is None:
            return None

        best_score: int | None = None
        runner_up_score: int | None = None
        for candidate in generate_legal_moves(board_before):
            child_board = Board(board_before.to_fen())
            child_board.make_move(candidate)
            candidate_score = self._normalize_review_score(-self.engine.iterative_deepening(child_board, max_depth=1).score)
            if candidate.uci() == best_move:
                best_score = candidate_score
                continue
            if runner_up_score is None or candidate_score > runner_up_score:
                runner_up_score = candidate_score

        if best_score is None or runner_up_score is None:
            return None
        return max(0, best_score - runner_up_score)

    def _piece_belongs_to_side_to_move(self, piece: str) -> bool:
        if piece == EMPTY:
            return False
        if self.board.side_to_move == WHITE:
            return piece.isupper()
        if self.board.side_to_move == BLACK:
            return piece.islower()
        return False

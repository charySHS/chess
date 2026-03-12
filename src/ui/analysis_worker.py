from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from math import isfinite
from pathlib import Path
from shutil import which

from src.chess_core import Board, generate_legal_moves
from src.config import AppConfig
from src.engine.profile import load_latest_engine_profile
from src.engine.search import SearchEngine, SearchResult
from src.engine.stockfish_bridge import MoveReview, Score, StockfishBridge, classify_move_loss


MATE_SCORE_CP = 100000


class AnalysisWorker:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="newchess-analysis")
        latest = load_latest_engine_profile(Path("artifacts/engine_snapshots"))
        self._search_engine = SearchEngine(profile=latest[0]) if latest is not None else SearchEngine()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def submit_engine_snapshot(self, fen: str, depth: int) -> Future[SearchResult]:
        return self._executor.submit(self._compute_snapshot, fen, depth)

    def submit_engine_move(self, fen: str, depth: int) -> Future[str | None]:
        return self._executor.submit(self._compute_engine_move, fen, depth)

    def submit_move_review(self, before_fen: str, move_uci: str) -> Future[MoveReview | None]:
        return self._executor.submit(self._compute_move_review, before_fen, move_uci)

    def _compute_snapshot(self, fen: str, depth: int) -> SearchResult:
        return self._search_engine.iterative_deepening(Board(fen), max_depth=depth)

    def _compute_engine_move(self, fen: str, depth: int) -> str | None:
        result = self._search_engine.iterative_deepening(Board(fen), max_depth=depth)
        return result.best_move.uci() if result.best_move is not None else None

    def _compute_move_review(self, before_fen: str, move_uci: str) -> MoveReview | None:
        board_before = Board(before_fen)
        move = next((candidate for candidate in generate_legal_moves(board_before) if candidate.uci() == move_uci), None)
        if move is None:
            return None

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

        best_result = self._search_engine.iterative_deepening(board_before, max_depth=fallback_depth)
        child_board = Board(before_fen)
        child_board.make_move(move)
        played_result = self._search_engine.iterative_deepening(child_board, max_depth=max(2, fallback_depth - 1))
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
            candidate_score = self._normalize_review_score(-self._search_engine.iterative_deepening(child_board, max_depth=1).score)
            if candidate.uci() == best_move:
                best_score = candidate_score
                continue
            if runner_up_score is None or candidate_score > runner_up_score:
                runner_up_score = candidate_score

        if best_score is None or runner_up_score is None:
            return None
        return max(0, best_score - runner_up_score)

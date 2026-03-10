from __future__ import annotations

from dataclasses import dataclass
from math import inf

from src.chess_core import WHITE, Board, Move, generate_legal_moves, is_checkmate, is_stalemate
from src.engine.evaluator import HybridEvaluator
from src.engine.ordering import order_moves
from src.engine.transposition import EXACT, LOWERBOUND, UPPERBOUND, TTEntry, TranspositionTable


@dataclass(frozen=True)
class SearchResult:
    best_move: Move | None
    score: float
    depth: int
    nodes: int


class SearchEngine:
    def __init__(self, evaluator: HybridEvaluator | None = None) -> None:
        self.evaluator = evaluator or HybridEvaluator()
        self.transposition_table = TranspositionTable()
        self.nodes_searched = 0

    def choose_move(self, board: Board, depth: int = 2):
        return self.iterative_deepening(board, max_depth=depth).best_move

    def iterative_deepening(self, board: Board, max_depth: int = 3) -> SearchResult:
        best_move = None
        best_score = -inf
        self.nodes_searched = 0

        for depth in range(1, max_depth + 1):
            move, score = self._search_root(board, depth)
            if move is not None:
                best_move = move
                best_score = score

        return SearchResult(
            best_move=best_move,
            score=best_score,
            depth=max_depth,
            nodes=self.nodes_searched,
        )

    def _search_root(self, board: Board, depth: int) -> tuple[Move | None, float]:
        alpha = -inf
        beta = inf
        best_score = -inf
        best_move = None

        ordered_moves = self._ordered_moves(board)
        for move in ordered_moves:
            child = Board(board.to_fen())
            child.make_move(move)
            score = -self._negamax(child, depth - 1, -beta, -alpha)
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)

        self.transposition_table.store(
            board.to_fen(),
            TTEntry(depth=depth, score=best_score, flag=EXACT, best_move_uci=best_move.uci() if best_move else None),
        )
        return best_move, best_score

    def _negamax(self, board: Board, depth: int, alpha: float, beta: float) -> float:
        self.nodes_searched += 1
        fen = board.to_fen()
        alpha_original = alpha
        beta_original = beta

        entry = self.transposition_table.get(fen)
        if entry is not None and entry.depth >= depth:
            if entry.flag == EXACT:
                return entry.score
            if entry.flag == LOWERBOUND:
                alpha = max(alpha, entry.score)
            elif entry.flag == UPPERBOUND:
                beta = min(beta, entry.score)
            if alpha >= beta:
                return entry.score

        if is_checkmate(board):
            return -100000.0 - depth
        if is_stalemate(board):
            return 0.0
        if depth == 0:
            signed = 1.0 if board.side_to_move == WHITE else -1.0
            return signed * self.evaluator.evaluate(board)

        best_score = -inf
        best_move = None
        for move in self._ordered_moves(board, entry.best_move_uci if entry else None):
            child = Board(fen)
            child.make_move(move)
            score = -self._negamax(child, depth - 1, -beta, -alpha)
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                break

        flag = EXACT
        if best_score <= alpha_original:
            flag = UPPERBOUND
        elif best_score >= beta_original:
            flag = LOWERBOUND

        self.transposition_table.store(
            fen,
            TTEntry(depth=depth, score=best_score, flag=flag, best_move_uci=best_move.uci() if best_move else None),
        )
        return best_score

    def _ordered_moves(self, board: Board, principal_variation_move: str | None = None) -> list[Move]:
        moves = order_moves(generate_legal_moves(board))
        if principal_variation_move is None:
            return moves

        pv_moves = [move for move in moves if move.uci() == principal_variation_move]
        remaining = [move for move in moves if move.uci() != principal_variation_move]
        return pv_moves + remaining

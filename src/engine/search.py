from __future__ import annotations

from dataclasses import dataclass
from math import inf
from pathlib import Path

from src.chess_core import WHITE, Board, Move, generate_legal_moves, is_checkmate, is_in_check, is_stalemate
from src.chess_core.constants import EMPTY
from src.config import AppConfig
from src.engine.evaluator import HybridEvaluator
from src.engine.ordering import move_ordering_key
from src.engine.profile import EngineProfile, SearchConfig
from src.engine.see import piece_value, static_exchange_eval
from src.engine.transposition import EXACT, LOWERBOUND, UPPERBOUND, TTEntry, TranspositionTable
from src.nn.infer import NeuralEvaluator


MATE_SCORE = 1000000.0


@dataclass(frozen=True)
class SearchResult:
    best_move: Move | None
    score: float
    depth: int
    nodes: int


class SearchEngine:
    def __init__(
        self,
        evaluator: HybridEvaluator | None = None,
        config: SearchConfig | None = None,
        profile: EngineProfile | None = None,
        model_path: Path | None = None,
    ) -> None:
        self.model_path = model_path
        if profile is not None:
            self.config = profile.search
            self.evaluator = evaluator or self._build_evaluator(profile)
        else:
            self.config = config or SearchConfig()
            self.evaluator = evaluator or self._build_evaluator()
        self.transposition_table = TranspositionTable()
        self.nodes_searched = 0
        self.killer_moves: dict[int, list[str]] = {}
        self.history_scores: dict[str, int] = {}

    def _build_evaluator(self, profile: EngineProfile | None = None) -> HybridEvaluator:
        neural = None
        model_path = self.model_path or AppConfig().model_path
        if Path(model_path).exists():
            try:
                neural = NeuralEvaluator.from_path(model_path)
            except Exception:
                neural = None
        if profile is not None:
            return HybridEvaluator.from_config(profile.evaluator, neural=neural)
        return HybridEvaluator(neural=neural)

    def choose_move(self, board: Board, depth: int = 2):
        return self.iterative_deepening(board, max_depth=depth).best_move

    def iterative_deepening(self, board: Board, max_depth: int = 3) -> SearchResult:
        best_move = None
        best_score = -inf
        self.nodes_searched = 0
        self.killer_moves.clear()

        for depth in range(1, max_depth + 1):
            if depth == 1 or best_score in (-inf, inf):
                move, score = self._search_root(board, depth, -inf, inf)
            else:
                window = self.config.aspiration_window
                alpha = best_score - window
                beta = best_score + window
                while True:
                    move, score = self._search_root(board, depth, alpha, beta)
                    if score <= alpha:
                        alpha -= window
                        window *= 2.0
                        continue
                    if score >= beta:
                        beta += window
                        window *= 2.0
                        continue
                    break
            if move is not None:
                best_move = move
                best_score = score

        return SearchResult(
            best_move=best_move,
            score=best_score,
            depth=max_depth,
            nodes=self.nodes_searched,
        )

    def _search_root(self, board: Board, depth: int, alpha: float, beta: float) -> tuple[Move | None, float]:
        alpha_original = alpha
        beta_original = beta
        best_score = -inf
        best_move = None

        ordered_moves = self._ordered_moves(board, ply=0)
        for move_index, move in enumerate(ordered_moves):
            board.make_move(move)
            if is_checkmate(board):
                board.undo_move()
                return move, MATE_SCORE + depth
            if move_index == 0:
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply=1)
            else:
                score = -self._negamax(board, depth - 1, -alpha - 1, -alpha, ply=1)
                if score > alpha and score < beta:
                    score = -self._negamax(board, depth - 1, -beta, -alpha, ply=1)
            board.undo_move()
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
            board.zobrist_key,
            TTEntry(depth=depth, score=best_score, flag=flag, best_move_uci=best_move.uci() if best_move else None),
        )
        return best_move, best_score

    def _negamax(self, board: Board, depth: int, alpha: float, beta: float, ply: int) -> float:
        self.nodes_searched += 1
        alpha_original = alpha
        beta_original = beta
        key = board.zobrist_key

        entry = self.transposition_table.get(key)
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
            return -MATE_SCORE - depth
        if is_stalemate(board) or board.is_threefold_repetition():
            return 0.0
        in_check = is_in_check(board)
        if depth <= 0:
            if in_check:
                depth = 1
            else:
                return self._quiescence(board, alpha, beta)

        if depth >= self.config.null_move_depth_trigger and not in_check and not self._is_zugzwang_prone(board):
            board.make_null_move()
            null_score = -self._negamax(
                board,
                depth - 1 - self.config.null_move_reduction,
                -beta,
                -beta + 1,
                ply + 1,
            )
            board.undo_null_move()
            if null_score >= beta:
                return beta

        best_score = -inf
        best_move = None
        ordered_moves = self._ordered_moves(board, principal_variation_move=entry.best_move_uci if entry else None, ply=ply)
        for move_index, move in enumerate(ordered_moves):
            board.make_move(move)
            quiet_move = move.captured == EMPTY and move.promotion is None and not move.is_en_passant
            if move_index == 0:
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            else:
                reduction = (
                    self.config.lmr_reduction
                    if depth >= self.config.lmr_depth_trigger
                    and move_index >= self.config.lmr_move_index_trigger
                    and quiet_move
                    and not in_check
                    else 0
                )
                search_depth = depth - 1 - reduction
                score = -self._negamax(board, search_depth, -alpha - 1, -alpha, ply + 1)
                if score > alpha and reduction:
                    score = -self._negamax(board, depth - 1, -alpha - 1, -alpha, ply + 1)
                if score > alpha and score < beta:
                    score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.undo_move()
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                if quiet_move:
                    self._record_killer(move.uci(), ply)
                    self.history_scores[move.uci()] = self.history_scores.get(move.uci(), 0) + depth * depth
                break

        flag = EXACT
        if best_score <= alpha_original:
            flag = UPPERBOUND
        elif best_score >= beta_original:
            flag = LOWERBOUND

        self.transposition_table.store(
            key,
            TTEntry(depth=depth, score=best_score, flag=flag, best_move_uci=best_move.uci() if best_move else None),
        )
        return best_score

    def _quiescence(self, board: Board, alpha: float, beta: float) -> float:
        self.nodes_searched += 1
        signed = 1.0 if board.side_to_move == WHITE else -1.0
        stand_pat = signed * self.evaluator.evaluate(board)
        if stand_pat >= beta:
            return beta
        alpha = max(alpha, stand_pat)

        capture_moves = [
            move
            for move in self._ordered_moves(board, ply=0, captures_only=True)
            if move.captured != "." or move.is_en_passant or move.promotion is not None
        ]
        for move in capture_moves:
            if move.captured != EMPTY and stand_pat + piece_value(move.captured) + self.config.delta_margin < alpha:
                continue
            if move.captured != EMPTY and move.promotion is None and not move.is_en_passant and static_exchange_eval(board, move) < 0:
                continue
            board.make_move(move)
            score = -self._quiescence(board, -beta, -alpha)
            board.undo_move()
            if score >= beta:
                return beta
            alpha = max(alpha, score)
        return alpha

    def _ordered_moves(
        self,
        board: Board,
        principal_variation_move: str | None = None,
        ply: int = 0,
        captures_only: bool = False,
    ) -> list[Move]:
        moves = generate_legal_moves(board)
        if captures_only:
            moves = [move for move in moves if move.captured != EMPTY or move.is_en_passant or move.promotion is not None]
        moves = sorted(moves, key=lambda move: self._tactical_move_key(board, move, ply), reverse=True)
        if principal_variation_move is None:
            return moves

        pv_moves = [move for move in moves if move.uci() == principal_variation_move]
        remaining = [move for move in moves if move.uci() != principal_variation_move]
        return pv_moves + remaining

    def _tactical_move_key(self, board: Board, move: Move, ply: int) -> tuple[int, int, int, int, int, int, int]:
        killer_bonus = int(move.uci() in self.killer_moves.get(ply, []))
        history_bonus = self.history_scores.get(move.uci(), 0)
        capture_bonus = 0
        see_bonus = 0
        if move.captured != EMPTY or move.is_en_passant:
            capture_bonus = piece_value(move.captured) * 16 - piece_value(move.piece)
            see_bonus = static_exchange_eval(board, move)
        promotion_bonus = piece_value(move.promotion) if move.promotion is not None else 0
        castling_bonus = 1 if move.is_castling else 0
        return (
            promotion_bonus,
            capture_bonus,
            see_bonus,
            killer_bonus,
            history_bonus,
            castling_bonus,
            *move_ordering_key(move),
        )

    def _record_killer(self, move_uci: str, ply: int) -> None:
        killers = self.killer_moves.setdefault(ply, [])
        if move_uci in killers:
            return
        killers.insert(0, move_uci)
        del killers[self.config.max_killers :]

    def _is_zugzwang_prone(self, board: Board) -> bool:
        non_pawn_non_king = 0
        for piece in board.squares:
            if piece in (EMPTY, "P", "p", "K", "k"):
                continue
            if (board.side_to_move == WHITE and piece.isupper()) or (board.side_to_move != WHITE and piece.islower()):
                non_pawn_non_king += 1
        return non_pawn_non_king == 0

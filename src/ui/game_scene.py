from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from time import perf_counter
from typing import Callable

import pygame

from src.chess_core import Board, Move, START_FEN, generate_legal_moves, is_checkmate, is_in_check, is_stalemate
from src.chess_core.constants import BLACK, EMPTY, WHITE
from src.engine.stockfish_bridge import MoveReview
from src.engine.search import SearchResult
from src.ui.analysis_worker import AnalysisWorker
from src.ui.board_renderer import (
    BoardLayout,
    BoardRenderer,
    MoveAnimationState,
    PromotionOverlayState,
    promotion_option_rects,
)
from src.ui.audio import AudioManager
from src.ui.input_handler import InputHandler, MoveResolution
from src.ui.theme import Theme


@dataclass(frozen=True)
class GameResult:
    is_over: bool
    headline: str
    winner: str | None = None
    reason: str | None = None


@dataclass
class PendingPromotion:
    moves: list[Move]


@dataclass
class ActiveMoveAnimation:
    piece: str
    from_square: int
    to_square: int
    captured_piece: str
    captured_square: int | None
    started_at: float
    duration: float = 0.18

    def snapshot(self) -> MoveAnimationState:
        progress = min(1.0, max(0.0, (perf_counter() - self.started_at) / self.duration))
        return MoveAnimationState(
            piece=self.piece,
            from_square=self.from_square,
            to_square=self.to_square,
            progress=progress,
            captured_piece=self.captured_piece,
            captured_square=self.captured_square,
        )


@dataclass
class AlertBanner:
    text: str
    started_at: float
    duration: float = 1.6

    def progress(self) -> float:
        return min(1.0, max(0.0, (perf_counter() - self.started_at) / self.duration))


class GameScene:
    ENGINE_DEPTH = 3

    def __init__(
        self,
        screen: pygame.Surface,
        theme: Theme | None = None,
        return_to_menu: Callable[[], None] | None = None,
        request_quit: Callable[[], None] | None = None,
        cycle_theme: Callable[[], None] | None = None,
    ) -> None:
        self.screen = screen
        self.theme = theme or Theme()
        self.board = Board(START_FEN)
        self.renderer = BoardRenderer(self.theme)
        self.flipped = False
        self.mode = "local"
        self.human_side = WHITE
        self.return_to_menu = return_to_menu or (lambda: None)
        self.request_quit = request_quit or (lambda: None)
        self.cycle_theme = cycle_theme or (lambda: None)
        self.legal_moves: list[Move] = []
        self.legal_moves_by_from: dict[int, list[Move]] = {}
        self.result = GameResult(False, "In Progress")
        self.pending_promotion: PendingPromotion | None = None
        self.move_scroll_offset = 0
        self.analysis_worker = AnalysisWorker()
        self.engine_snapshot: SearchResult | None = None
        self.last_review: MoveReview | None = None
        self.active_animation: ActiveMoveAnimation | None = None
        self.audio = AudioManager()
        self.rook_alert: AlertBanner | None = None
        self.entered_at = perf_counter()
        self.engine_snapshot_future: Future[SearchResult] | None = None
        self.engine_snapshot_fen: str | None = None
        self.engine_move_future: Future[str | None] | None = None
        self.engine_move_fen: str | None = None
        self.review_future: Future[MoveReview | None] | None = None
        self.review_target: tuple[str, str] | None = None
        self.input_handler = InputHandler(
            square_at_pixel=self.square_at_pixel,
            piece_at_square=self.piece_at_square,
            legal_moves_for_square=self.legal_moves_for_square,
            resolve_move_choice=self.resolve_move_choice,
            apply_move=self.apply_move,
            reset_board=self.reset_board,
            undo_move=self.undo_last_move,
            toggle_flip=self.toggle_flip,
            cycle_theme=self.cycle_theme,
            return_to_menu=self.handle_return_to_menu,
            request_quit=self.request_quit,
            interaction_allowed=self.interaction_allowed,
        )
        self.refresh_legal_moves()

    def activate(self) -> None:
        self.entered_at = perf_counter()
        self.active_animation = None
        self.rook_alert = None

    def close(self) -> None:
        self._clear_background_requests()
        self.analysis_worker.shutdown()

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.renderer = BoardRenderer(theme)

    def set_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen

    def configure_mode(self, mode: str) -> None:
        self.mode = mode
        self.human_side = WHITE
        self._sync_local_orientation()

    def update(self) -> None:
        self._update_animation()
        self._update_alerts()
        self._poll_background_work()
        if self.mode != "engine":
            return
        if self.pending_promotion is not None or self.result.is_over:
            return
        if self.board.side_to_move == self.human_side:
            return
        self._ensure_engine_move_request()

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.pending_promotion is not None and self._handle_promotion_event(event):
            return
        if event.type == pygame.MOUSEWHEEL:
            self._handle_mousewheel(event)
            return
        self.input_handler.handle_event(event)

    def draw(self) -> None:
        captured_by_white, captured_by_black = self.captured_pieces()
        self.renderer.draw(
            surface=self.screen,
            board=self.board,
            input_state=self.input_handler.state,
            status_text=self.status_text(),
            review_text=self.review_summary(),
            detail_lines=self.detail_lines(),
            engine_lines=self.engine_lines(),
            review_badge=self.review_badge(),
            captured_by_white=captured_by_white,
            captured_by_black=captured_by_black,
            move_rows=self.move_rows(),
            move_scroll_offset=self.move_scroll_offset,
            flipped=self.flipped,
            last_move=self.last_move(),
            game_over_message=self.game_over_message(),
            promotion_overlay=self.promotion_overlay_state(),
            move_animation=self.move_animation_state(),
            intro_progress=self.intro_progress(),
            rook_alert_text=self.rook_alert_text(),
            animation_phase=pygame.time.get_ticks() / 1000.0,
        )
        pygame.display.flip()

    def refresh_legal_moves(self) -> None:
        self.legal_moves = generate_legal_moves(self.board)
        grouped: dict[int, list[Move]] = {}
        for move in self.legal_moves:
            grouped.setdefault(move.from_square, []).append(move)
        self.legal_moves_by_from = grouped
        self.result = self.evaluate_result()
        self._snap_scroll_to_latest()
        self._refresh_engine_snapshot()

    def reset_board(self) -> None:
        self.board = Board(START_FEN)
        self.pending_promotion = None
        self.move_scroll_offset = 0
        self.last_review = None
        self.active_animation = None
        self.rook_alert = None
        self._clear_background_requests()
        self.input_handler.reset_interaction()
        self._sync_local_orientation()
        self.refresh_legal_moves()

    def undo_last_move(self) -> None:
        self.board.undo_move()
        self.pending_promotion = None
        self.last_review = None
        self.active_animation = None
        self.rook_alert = None
        self._clear_background_requests()
        self.input_handler.reset_interaction()
        self._sync_local_orientation()
        self.refresh_legal_moves()

    def toggle_flip(self) -> None:
        self.flipped = not self.flipped

    def handle_return_to_menu(self) -> None:
        self.pending_promotion = None
        self.input_handler.reset_interaction()
        self.return_to_menu()

    def interaction_allowed(self) -> bool:
        return (
            not self.result.is_over
            and self.pending_promotion is None
            and (self.mode != "engine" or self.board.side_to_move == self.human_side)
        )

    def square_at_pixel(self, point: tuple[int, int]) -> int | None:
        return self.layout().square_at_pixel(point)

    def layout(self) -> BoardLayout:
        return BoardLayout(*self.theme.board_origin, self.theme.square_size, self.flipped)

    def piece_at_square(self, square: int) -> str:
        return self.board.piece_at(square)

    def legal_moves_for_square(self, square: int) -> list[Move]:
        piece = self.board.piece_at(square)
        if not self._piece_belongs_to_side_to_move(piece):
            return []
        return list(self.legal_moves_by_from.get(square, []))

    def apply_move(self, move: Move) -> None:
        board_before = Board(self.board.to_fen())
        moving_piece = self.board.piece_at(move.from_square)
        captured_piece = self.board.piece_at(move.to_square)
        captured_square = move.to_square
        if move.is_en_passant:
            captured_square = self.board._en_passant_capture_square(move.to_square, moving_piece)
            captured_piece = self.board.piece_at(captured_square)

        self.board.make_move(move)
        self.active_animation = ActiveMoveAnimation(
            piece=move.promotion if move.promotion is not None else moving_piece,
            from_square=move.from_square,
            to_square=move.to_square,
            captured_piece=captured_piece,
            captured_square=captured_square if captured_piece != EMPTY else None,
            started_at=perf_counter(),
        )
        if captured_piece.lower() == "r":
            self.rook_alert = AlertBanner("Rook down.", perf_counter())
            self.audio.play_rook_alert()
        self.pending_promotion = None
        self.last_review = None
        self._request_move_review(board_before.to_fen(), move.uci())
        self._sync_local_orientation()
        self.refresh_legal_moves()

    def resolve_move_choice(self, moves: list[Move]) -> MoveResolution:
        if not moves:
            return MoveResolution()
        if len(moves) > 1 and all(move.promotion is not None for move in moves):
            ordered = sorted(moves, key=lambda move: "QRBN".index(move.promotion.upper()))
            self.pending_promotion = PendingPromotion(ordered)
            return MoveResolution(awaiting_choice=True)
        return MoveResolution(move=moves[0])

    def last_move(self) -> Move | None:
        if not self.board.history:
            return None
        return self.board.history[-1].move

    def status_text(self) -> str:
        side = "White" if self.board.side_to_move == WHITE else "Black"
        mode_label = "Engine" if self.mode == "engine" else "Local"
        tags: list[str] = [f"Turn: {side}", f"Mode: {mode_label}", f"Theme: {self.theme.name.title()}"]
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
            f"{'Human vs Engine' if self.mode == 'engine' else 'Local pass-and-play'}",
            f"{side} to move",
            f"{len(self.legal_moves)} legal moves  |  Last: {self.last_move().uci() if self.last_move() else '--'}",
        ]
        if self.result.is_over:
            lines.append(f"Result: {self.result.headline}")
        elif self.pending_promotion is not None:
            lines.append("Promotion pending")
        elif is_in_check(self.board):
            lines.append(f"{side} is in check")
        else:
            lines.append("Position is stable")
        return lines

    def engine_lines(self) -> list[str]:
        if self.engine_snapshot is None or self.engine_snapshot.best_move is None:
            return [
                "Engine: thinking" if self.engine_snapshot_future is not None else "Engine: waiting",
                "Best move: --",
                "Eval: --",
                "Depth: --",
            ]

        return [
            f"Engine: {'active' if self.mode == 'engine' else 'analysis'}",
            f"Best move: {self.engine_snapshot.best_move.uci()}",
            f"Eval: {self.engine_snapshot.score:.1f}",
            f"Depth {self.engine_snapshot.depth}  Nodes {self.engine_snapshot.nodes}",
        ]

    def review_badge(self) -> str | None:
        if self.last_review is None:
            return None
        return self.last_review.label

    def review_summary(self) -> str:
        if self.last_review is None:
            if self.review_future is not None:
                return "Review in progress. The UI stays responsive while the analysis thread scores the last move."
            return "Review will appear here after each move. Best line, score swing, and move quality stay visible while you play."

        best_move = self.last_review.best_move or "--"
        played_cp = self.last_review.played_score.as_centipawns()
        best_cp = self.last_review.best_score.as_centipawns()
        return (
            f"{self.last_review.label.title()}  |  Played {self.last_review.played_move}  |  "
            f"Best {best_move}  |  Loss {self.last_review.loss_cp} cp  |  "
            f"Eval {played_cp / 100:.2f} vs {best_cp / 100:.2f}"
        )

    def move_rows(self) -> list[str]:
        rows: list[str] = []
        history = self.board.history
        for index in range(0, len(history), 2):
            move_number = index // 2 + 1
            white_move = history[index].move.uci()
            black_move = history[index + 1].move.uci() if index + 1 < len(history) else ""
            rows.append(f"{move_number}. {white_move} {black_move}".rstrip())
        return rows

    def _handle_mousewheel(self, event: pygame.event.Event) -> None:
        if not self._move_history_rect().collidepoint(pygame.mouse.get_pos()):
            return

        row_count = len(self.move_rows())
        visible_count = 2
        max_offset = max(0, row_count - visible_count)
        self.move_scroll_offset = max(0, min(self.move_scroll_offset - event.y, max_offset))

    def _move_history_rect(self) -> pygame.Rect:
        panel_x, panel_y, panel_width, _ = self.theme.side_panel_rect
        return pygame.Rect(panel_x + 16, panel_y + 436, panel_width - 32, 124)

    def _snap_scroll_to_latest(self) -> None:
        row_count = len(self.move_rows())
        visible_count = 2
        self.move_scroll_offset = max(0, row_count - visible_count)

    def _refresh_engine_snapshot(self) -> None:
        if self.result.is_over or not self.legal_moves:
            self.engine_snapshot = None
            self.engine_snapshot_future = None
            self.engine_snapshot_fen = None
            return
        fen = self.board.to_fen()
        if self.engine_snapshot_future is not None and self.engine_snapshot_fen == fen:
            return
        self.engine_snapshot_future = self.analysis_worker.submit_engine_snapshot(fen, self.ENGINE_DEPTH)
        self.engine_snapshot_fen = fen

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

    def game_over_message(self) -> str | None:
        if not self.result.is_over:
            return None
        return self.result.headline

    def promotion_overlay_state(self) -> PromotionOverlayState | None:
        if self.pending_promotion is None:
            return None
        return PromotionOverlayState(self.pending_promotion.moves)

    def move_animation_state(self) -> MoveAnimationState | None:
        if self.active_animation is None:
            return None
        return self.active_animation.snapshot()

    def intro_progress(self) -> float:
        return min(1.0, max(0.0, (perf_counter() - self.entered_at) / 0.45))

    def rook_alert_text(self) -> str | None:
        if self.rook_alert is None:
            return None
        if self.rook_alert.progress() >= 1.0:
            return None
        return self.rook_alert.text

    def evaluate_result(self) -> GameResult:
        if is_checkmate(self.board):
            winner = "Black" if self.board.side_to_move == WHITE else "White"
            return GameResult(True, f"Checkmate: {winner} wins", winner=winner, reason="checkmate")
        if self.board.is_threefold_repetition():
            return GameResult(True, "Draw by repetition", reason="repetition")
        if is_stalemate(self.board):
            return GameResult(True, "Draw by stalemate", reason="stalemate")
        return GameResult(False, "In Progress")

    def _sync_local_orientation(self) -> None:
        if self.mode == "local":
            self.flipped = self.board.side_to_move == BLACK

    def _handle_promotion_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            self.request_quit()
            return True
        if event.type == pygame.KEYDOWN:
            mapping = {
                pygame.K_q: "Q",
                pygame.K_r: "R",
                pygame.K_b: "B",
                pygame.K_n: "N",
            }
            promotion_code = mapping.get(event.key)
            if promotion_code is not None:
                return self._apply_promotion_by_code(promotion_code)
            if event.key == pygame.K_ESCAPE:
                self.pending_promotion = None
                self.input_handler.reset_interaction()
                return True
            if event.key == pygame.K_t:
                self.cycle_theme()
                return True
            if event.key == pygame.K_m:
                self.handle_return_to_menu()
                return True
            if event.key == pygame.K_r:
                self.reset_board()
                return True
            if event.key == pygame.K_u:
                self.undo_last_move()
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.pending_promotion is not None:
            for rect, move in zip(promotion_option_rects(self.theme), self.pending_promotion.moves, strict=True):
                if rect.collidepoint(event.pos):
                    self.apply_move(move)
                    self.input_handler.reset_interaction()
                    return True
        return False

    def _apply_promotion_by_code(self, promotion_code: str) -> bool:
        if self.pending_promotion is None:
            return False
        for move in self.pending_promotion.moves:
            if move.promotion is not None and move.promotion.upper() == promotion_code:
                self.apply_move(move)
                self.input_handler.reset_interaction()
                return True
        return False

    def _piece_belongs_to_side_to_move(self, piece: str) -> bool:
        if piece == EMPTY:
            return False
        if self.board.side_to_move == WHITE:
            return piece.isupper()
        if self.board.side_to_move == BLACK:
            return piece.islower()
        return False

    def _update_animation(self) -> None:
        if self.active_animation is None:
            return
        if self.active_animation.snapshot().progress >= 1.0:
            self.active_animation = None

    def _update_alerts(self) -> None:
        if self.rook_alert is not None and self.rook_alert.progress() >= 1.0:
            self.rook_alert = None

    def _request_move_review(self, before_fen: str, move_uci: str) -> None:
        self.review_future = self.analysis_worker.submit_move_review(before_fen, move_uci)
        self.review_target = (before_fen, move_uci)

    def _ensure_engine_move_request(self) -> None:
        fen = self.board.to_fen()
        if self.engine_move_future is not None and self.engine_move_fen == fen:
            return
        self.engine_move_future = self.analysis_worker.submit_engine_move(fen, self.ENGINE_DEPTH)
        self.engine_move_fen = fen

    def _poll_background_work(self) -> None:
        current_fen = self.board.to_fen()

        if self.engine_snapshot_future is not None and self.engine_snapshot_future.done():
            try:
                snapshot = self.engine_snapshot_future.result()
            except Exception:
                snapshot = None
            if snapshot is not None and self.engine_snapshot_fen == current_fen:
                self.engine_snapshot = snapshot
            self.engine_snapshot_future = None
            self.engine_snapshot_fen = None

        if self.review_future is not None and self.review_future.done():
            try:
                review = self.review_future.result()
            except Exception:
                review = None
            if self.review_target is not None and self.review_target[0] == self._board_before_last_move_fen():
                self.last_review = review
            self.review_future = None
            self.review_target = None

        if self.engine_move_future is not None and self.engine_move_future.done():
            try:
                move_uci = self.engine_move_future.result()
            except Exception:
                move_uci = None
            target_fen = self.engine_move_fen
            self.engine_move_future = None
            self.engine_move_fen = None
            if target_fen != current_fen or move_uci is None or self.mode != "engine" or self.result.is_over:
                return
            move = next((candidate for candidate in self.legal_moves if candidate.uci() == move_uci), None)
            if move is not None and self.board.side_to_move != self.human_side:
                self.apply_move(move)

    def _board_before_last_move_fen(self) -> str | None:
        if not self.board.history:
            return None
        board_before = Board(self.board.to_fen())
        board_before.undo_move()
        return board_before.to_fen()

    def _clear_background_requests(self) -> None:
        if self.engine_snapshot_future is not None:
            self.engine_snapshot_future.cancel()
        self.engine_snapshot_future = None
        self.engine_snapshot_fen = None
        if self.engine_move_future is not None:
            self.engine_move_future.cancel()
        self.engine_move_future = None
        self.engine_move_fen = None
        if self.review_future is not None:
            self.review_future.cancel()
        self.review_future = None
        self.review_target = None

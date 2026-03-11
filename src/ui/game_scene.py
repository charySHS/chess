from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Callable

import pygame

from src.chess_core import Board, Move, START_FEN, generate_legal_moves, is_checkmate, is_in_check, is_stalemate
from src.chess_core.constants import BLACK, EMPTY, WHITE
from src.config import AppConfig
from src.engine.stockfish_bridge import MoveReview, Score, StockfishBridge, classify_move_loss
from src.engine.search import SearchEngine, SearchResult
from src.ui.board_renderer import BoardLayout, BoardRenderer, PromotionOverlayState, promotion_option_rects
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


class GameScene:
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
        self.engine = SearchEngine()
        self.engine_snapshot: SearchResult | None = None
        self.last_review: MoveReview | None = None
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

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.renderer = BoardRenderer(theme)

    def configure_mode(self, mode: str) -> None:
        self.mode = mode
        self.human_side = WHITE

    def update(self) -> None:
        if self.mode != "engine":
            return
        if self.pending_promotion is not None or self.result.is_over:
            return
        if self.board.side_to_move == self.human_side:
            return

        engine_move = self.engine.choose_move(self.board, depth=2)
        if engine_move is None:
            return
        self.apply_move(engine_move)

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
        self.input_handler.reset_interaction()
        self.refresh_legal_moves()

    def undo_last_move(self) -> None:
        self.board.undo_move()
        self.pending_promotion = None
        self.last_review = None
        self.input_handler.reset_interaction()
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
        self.board.make_move(move)
        self.pending_promotion = None
        self.last_review = self._review_move(board_before, move)
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
        else:
            lines.append("Position is stable")
        return lines

    def engine_lines(self) -> list[str]:
        if self.engine_snapshot is None or self.engine_snapshot.best_move is None:
            return [
                "Engine: waiting",
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
        return pygame.Rect(panel_x + 16, panel_y + 486, panel_width - 32, 76)

    def _snap_scroll_to_latest(self) -> None:
        row_count = len(self.move_rows())
        visible_count = 2
        self.move_scroll_offset = max(0, row_count - visible_count)

    def _refresh_engine_snapshot(self) -> None:
        if self.result.is_over or not self.legal_moves:
            self.engine_snapshot = None
            return
        self.engine_snapshot = self.engine.iterative_deepening(self.board, max_depth=2)

    def _review_move(self, board_before: Board, move: Move) -> MoveReview | None:
        stockfish_path = AppConfig().stockfish_path
        if which(stockfish_path) or Path(stockfish_path).exists():
            try:
                with StockfishBridge(path=stockfish_path) as bridge:
                    return bridge.review_move(board_before, move, depth=8)
            except Exception:
                pass

        best_result = self.engine.iterative_deepening(board_before, max_depth=2)
        child_board = Board(board_before.to_fen())
        child_board.make_move(move)
        played_result = self.engine.iterative_deepening(child_board, max_depth=1)
        best_score = int(best_result.score if best_result.best_move is not None else 0)
        played_score = int(-played_result.score)
        loss_cp = max(0, best_score - played_score)
        best_move = best_result.best_move.uci() if best_result.best_move is not None else None
        return MoveReview(
            played_move=move.uci(),
            best_move=best_move,
            played_score=Score(cp=played_score),
            best_score=Score(cp=best_score),
            loss_cp=loss_cp,
            label=classify_move_loss(loss_cp, move.uci(), best_move),
        )

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

    def evaluate_result(self) -> GameResult:
        if is_checkmate(self.board):
            winner = "Black" if self.board.side_to_move == WHITE else "White"
            return GameResult(True, f"Checkmate: {winner} wins", winner=winner, reason="checkmate")
        if is_stalemate(self.board):
            return GameResult(True, "Draw by stalemate", reason="stalemate")
        return GameResult(False, "In Progress")

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

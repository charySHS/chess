from __future__ import annotations

from dataclasses import dataclass

import pygame

from src.chess_core.board import Board
from src.chess_core.constants import EMPTY
from src.chess_core.move import Move
from src.ui.input_handler import InputState
from src.ui.theme import LEGACY_FILENAME_MAP, PIECE_CODE_TO_NAME, Theme, sprite_directory_candidates


@dataclass(frozen=True)
class BoardLayout:
    origin_x: int
    origin_y: int
    square_size: int
    flipped: bool = False

    def square_rect(self, square: int) -> pygame.Rect:
        row = square // 8
        col = square % 8
        display_row = 7 - row if self.flipped else row
        display_col = 7 - col if self.flipped else col
        return pygame.Rect(
            self.origin_x + display_col * self.square_size,
            self.origin_y + display_row * self.square_size,
            self.square_size,
            self.square_size,
        )

    def square_at_pixel(self, point: tuple[int, int]) -> int | None:
        px, py = point
        board_px = px - self.origin_x
        board_py = py - self.origin_y
        if board_px < 0 or board_py < 0:
            return None

        col = board_px // self.square_size
        row = board_py // self.square_size
        if col > 7 or row > 7:
            return None

        board_row = 7 - row if self.flipped else row
        board_col = 7 - col if self.flipped else col
        return board_row * 8 + board_col


@dataclass(frozen=True)
class PromotionOption:
    piece: str
    rect: pygame.Rect


@dataclass(frozen=True)
class PromotionOverlayState:
    moves: list[Move]


def promotion_option_rects(theme: Theme) -> list[pygame.Rect]:
    board_x, board_y = theme.board_origin
    start_x = board_x + (theme.board_size - 4 * 88) // 2
    y = board_y + theme.board_size // 2 - 44
    return [pygame.Rect(start_x + index * 88, y, 80, 88) for index in range(4)]


class PieceSpriteStore:
    def __init__(self, theme: Theme) -> None:
        self.normal = self._load_scaled_set(theme.piece_size_normal)
        self.dragged = self._load_scaled_set(theme.piece_size_dragged)
        self.preview = self._load_scaled_set(64)

    def _load_scaled_set(self, target_size: int) -> dict[str, pygame.Surface]:
        sprites: dict[str, pygame.Surface] = {}
        for piece_code, asset_code in PIECE_CODE_TO_NAME.items():
            sprites[piece_code] = self._load_piece_surface(asset_code, target_size)
        return sprites

    def _load_piece_surface(self, asset_code: str, target_size: int) -> pygame.Surface:
        candidate_filenames = [f"{asset_code}.png", LEGACY_FILENAME_MAP[asset_code]]
        for directory in sprite_directory_candidates(target_size):
            for filename in candidate_filenames:
                asset_path = directory / filename
                if asset_path.exists():
                    surface = pygame.image.load(str(asset_path)).convert_alpha()
                    if surface.get_size() != (target_size, target_size):
                        surface = pygame.transform.smoothscale(surface, (target_size, target_size))
                    return surface
        searched = ", ".join(str(path) for path in sprite_directory_candidates(target_size))
        raise FileNotFoundError(f"Missing sprite for '{asset_code}' at size {target_size}. Searched: {searched}")


class BoardRenderer:
    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self.sprites = PieceSpriteStore(theme)
        self.coord_font = pygame.font.SysFont("arial", theme.label_font_size)
        self.status_font = pygame.font.SysFont("arial", theme.status_font_size)
        self.panel_title_font = pygame.font.SysFont("georgia", theme.panel_title_font_size, bold=True)
        self.panel_body_font = pygame.font.SysFont("arial", theme.panel_body_font_size)
        self.panel_small_font = pygame.font.SysFont("arial", theme.panel_small_font_size)

    def draw(
        self,
        surface: pygame.Surface,
        board: Board,
        input_state: InputState,
        status_text: str,
        detail_lines: list[str],
        captured_by_white: list[str],
        captured_by_black: list[str],
        move_rows: list[str],
        move_scroll_offset: int,
        flipped: bool,
        last_move: Move | None,
        game_over_message: str | None,
        promotion_overlay: PromotionOverlayState | None,
    ) -> None:
        surface.fill(self.theme.background)
        layout = BoardLayout(*self.theme.board_origin, self.theme.square_size, flipped)
        self._draw_status_panel(surface, status_text)
        self._draw_side_panel(
            surface,
            detail_lines,
            captured_by_white,
            captured_by_black,
            move_rows,
            move_scroll_offset,
        )
        self._draw_board(surface, layout)
        self._draw_last_move(surface, layout, last_move)
        self._draw_selected_square(surface, layout, input_state.selected_square)
        self._draw_legal_moves(surface, layout, input_state.legal_moves)
        self._draw_coordinates(surface, layout)
        self._draw_pieces(surface, board, layout, input_state)
        self._draw_dragged_piece(surface, board, input_state)
        self._draw_game_over_overlay(surface, game_over_message)
        self._draw_promotion_overlay(surface, promotion_overlay)

    def _draw_status_panel(self, surface: pygame.Surface, status_text: str) -> None:
        panel_rect = pygame.Rect(0, self.theme.window_height - self.theme.status_height, self.theme.window_width, self.theme.status_height)
        pygame.draw.rect(surface, self.theme.panel_background, panel_rect)
        status_surface = self.status_font.render(status_text, True, self.theme.status_text)
        surface.blit(status_surface, (self.theme.board_margin, self.theme.window_height - self.theme.status_height + 24))

    def _draw_side_panel(
        self,
        surface: pygame.Surface,
        detail_lines: list[str],
        captured_by_white: list[str],
        captured_by_black: list[str],
        move_rows: list[str],
        move_scroll_offset: int,
    ) -> None:
        rect = pygame.Rect(self.theme.side_panel_rect)
        pygame.draw.rect(surface, self.theme.side_panel_background, rect, border_radius=18)
        pygame.draw.rect(surface, self.theme.side_panel_accent, rect, width=2, border_radius=18)

        title = self.panel_title_font.render("Match", True, self.theme.heading_text)
        surface.blit(title, (rect.x + 20, rect.y + 18))

        for index, line in enumerate(detail_lines):
            body = self.panel_body_font.render(line, True, self.theme.muted_text)
            surface.blit(body, (rect.x + 20, rect.y + 76 + index * 30))

        capture_y = rect.y + 220
        heading = self.panel_title_font.render("Captures", True, self.theme.heading_text)
        surface.blit(heading, (rect.x + 20, capture_y))
        self._draw_capture_row(surface, rect.x + 20, capture_y + 44, "White", captured_by_white)
        self._draw_capture_row(surface, rect.x + 20, capture_y + 100, "Black", captured_by_black)

        moves_y = rect.y + 382
        moves_heading = self.panel_title_font.render("Moves", True, self.theme.heading_text)
        surface.blit(moves_heading, (rect.x + 20, moves_y))
        move_area = pygame.Rect(rect.x + 16, moves_y + 40, rect.width - 32, 126)
        self._draw_move_history(surface, move_area, move_rows, move_scroll_offset)

        shortcut_y = rect.bottom - 136
        controls = self.panel_title_font.render("Controls", True, self.theme.heading_text)
        surface.blit(controls, (rect.x + 20, shortcut_y))
        shortcuts = ["Esc Quit", "M Menu", "R Reset", "U Undo", "F Flip", "T Theme"]
        for index, label in enumerate(shortcuts):
            line = self.panel_small_font.render(label, True, self.theme.muted_text)
            surface.blit(line, (rect.x + 20, shortcut_y + 36 + index * 16))

    def _draw_capture_row(self, surface: pygame.Surface, x: int, y: int, label: str, pieces: list[str]) -> None:
        text = self.panel_small_font.render(label, True, self.theme.heading_text)
        surface.blit(text, (x, y))
        for index, piece in enumerate(pieces[:8]):
            sprite = self.sprites.preview[piece]
            surface.blit(sprite, (x + 58 + index * 28, y - 6))

    def _draw_move_history(
        self,
        surface: pygame.Surface,
        area: pygame.Rect,
        move_rows: list[str],
        move_scroll_offset: int,
    ) -> None:
        pygame.draw.rect(surface, self.theme.panel_background, area, border_radius=10)
        pygame.draw.rect(surface, self.theme.side_panel_accent, area, width=1, border_radius=10)

        rows = move_rows or ["1. --"]
        line_height = 22
        visible_count = max(1, (area.height - 12) // line_height)
        max_offset = max(0, len(rows) - visible_count)
        start_index = max(0, min(move_scroll_offset, max_offset))
        visible_rows = rows[start_index : start_index + visible_count]

        previous_clip = surface.get_clip()
        surface.set_clip(area.inflate(-8, -8))
        for index, row in enumerate(visible_rows):
            line = self.panel_small_font.render(row, True, self.theme.muted_text)
            surface.blit(line, (area.x + 12, area.y + 8 + index * line_height))
        surface.set_clip(previous_clip)

        if max_offset > 0:
            track = pygame.Rect(area.right - 10, area.y + 8, 4, area.height - 16)
            pygame.draw.rect(surface, self.theme.side_panel_background, track, border_radius=4)
            thumb_height = max(18, int(track.height * (visible_count / len(rows))))
            scroll_ratio = start_index / max_offset if max_offset else 0.0
            thumb_y = track.y + int((track.height - thumb_height) * scroll_ratio)
            thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_height)
            pygame.draw.rect(surface, self.theme.side_panel_accent, thumb, border_radius=4)

    def _draw_board(self, surface: pygame.Surface, layout: BoardLayout) -> None:
        for square in range(64):
            rect = layout.square_rect(square)
            row = square // 8
            col = square % 8
            color = self.theme.light_square if (row + col) % 2 == 0 else self.theme.dark_square
            pygame.draw.rect(surface, color, rect)

    def _draw_last_move(self, surface: pygame.Surface, layout: BoardLayout, last_move: Move | None) -> None:
        if last_move is None:
            return
        overlay = pygame.Surface((self.theme.square_size, self.theme.square_size), pygame.SRCALPHA)
        overlay.fill(self.theme.last_move_fill)
        for square in (last_move.from_square, last_move.to_square):
            surface.blit(overlay, layout.square_rect(square).topleft)

    def _draw_selected_square(self, surface: pygame.Surface, layout: BoardLayout, square: int | None) -> None:
        if square is None:
            return
        rect = layout.square_rect(square)
        pygame.draw.rect(surface, self.theme.selected_outline, rect.inflate(-6, -6), width=self.theme.selected_outline_width, border_radius=6)

    def _draw_legal_moves(self, surface: pygame.Surface, layout: BoardLayout, legal_moves: list[Move]) -> None:
        for move in legal_moves:
            rect = layout.square_rect(move.to_square)
            if move.captured != EMPTY or move.is_en_passant:
                ring = pygame.Surface((self.theme.square_size, self.theme.square_size), pygame.SRCALPHA)
                pygame.draw.circle(ring, self.theme.legal_capture_outline, (self.theme.square_size // 2, self.theme.square_size // 2), self.theme.square_size // 2 - 8, width=self.theme.capture_ring_width)
                surface.blit(ring, rect.topleft)
            else:
                dot = pygame.Surface((self.theme.square_size, self.theme.square_size), pygame.SRCALPHA)
                pygame.draw.circle(dot, self.theme.legal_quiet_fill, (self.theme.square_size // 2, self.theme.square_size // 2), self.theme.quiet_move_radius)
                surface.blit(dot, rect.topleft)

    def _draw_coordinates(self, surface: pygame.Surface, layout: BoardLayout) -> None:
        files = "abcdefgh"
        ranks = "87654321"
        if layout.flipped:
            files = files[::-1]
            ranks = ranks[::-1]
        for display_col, file_char in enumerate(files):
            text = self.coord_font.render(file_char, True, self.theme.coord_text)
            surface.blit(text, (layout.origin_x + display_col * layout.square_size + layout.square_size - 16, layout.origin_y + 8 * layout.square_size + 4))
        for display_row, rank_char in enumerate(ranks):
            text = self.coord_font.render(rank_char, True, self.theme.coord_text)
            surface.blit(text, (layout.origin_x - 16, layout.origin_y + display_row * layout.square_size + 6))

    def _draw_pieces(self, surface: pygame.Surface, board: Board, layout: BoardLayout, input_state: InputState) -> None:
        hidden_square = input_state.drag_origin if input_state.is_dragging else None
        for square, piece in enumerate(board.squares):
            if piece == EMPTY or square == hidden_square:
                continue
            surface.blit(self.sprites.normal[piece], layout.square_rect(square).topleft)

    def _draw_dragged_piece(self, surface: pygame.Surface, board: Board, input_state: InputState) -> None:
        if not input_state.is_dragging or input_state.drag_origin is None or input_state.drag_position is None:
            return
        piece = board.piece_at(input_state.drag_origin)
        if piece == EMPTY:
            return
        sprite = self.sprites.dragged[piece]
        shadow = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        shadow.fill(self.theme.drag_shadow)
        rect = sprite.get_rect(center=input_state.drag_position)
        surface.blit(shadow, rect.move(3, 4))
        surface.blit(sprite, rect)

    def _draw_game_over_overlay(self, surface: pygame.Surface, game_over_message: str | None) -> None:
        if game_over_message is None:
            return
        overlay = pygame.Surface((self.theme.board_size, self.theme.board_size), pygame.SRCALPHA)
        overlay.fill(self.theme.overlay_fill)
        surface.blit(overlay, self.theme.board_origin)
        banner = pygame.Rect(0, 0, 360, 124)
        board_x, board_y = self.theme.board_origin
        banner.center = (board_x + self.theme.board_size // 2, board_y + self.theme.board_size // 2)
        pygame.draw.rect(surface, self.theme.win_banner, banner, border_radius=18)
        pygame.draw.rect(surface, self.theme.side_panel_accent, banner, width=2, border_radius=18)
        title = self.panel_title_font.render("Game Over", True, self.theme.win_banner_text)
        message = self.panel_body_font.render(game_over_message, True, self.theme.win_banner_text)
        hint = self.coord_font.render("Press R to restart or M for menu", True, self.theme.win_banner_text)
        surface.blit(title, title.get_rect(center=(banner.centerx, banner.y + 32)))
        surface.blit(message, message.get_rect(center=(banner.centerx, banner.y + 68)))
        surface.blit(hint, hint.get_rect(center=(banner.centerx, banner.y + 100)))

    def _draw_promotion_overlay(self, surface: pygame.Surface, promotion_overlay: PromotionOverlayState | None) -> None:
        if promotion_overlay is None:
            return
        overlay = pygame.Surface((self.theme.board_size, self.theme.board_size), pygame.SRCALPHA)
        overlay.fill(self.theme.overlay_fill)
        surface.blit(overlay, self.theme.board_origin)
        title_rect = pygame.Rect(self.theme.board_origin[0] + 156, self.theme.board_origin[1] + 218, 328, 44)
        title = self.panel_body_font.render("Choose promotion", True, self.theme.heading_text)
        surface.blit(title, title.get_rect(center=title_rect.center))
        for move, rect in zip(promotion_overlay.moves, promotion_option_rects(self.theme), strict=True):
            pygame.draw.rect(surface, self.theme.promotion_panel, rect, border_radius=12)
            pygame.draw.rect(surface, self.theme.side_panel_accent, rect, width=2, border_radius=12)
            piece = move.promotion if move.promotion is not None else move.piece
            sprite = self.sprites.preview[piece]
            sprite_rect = sprite.get_rect(center=(rect.centerx, rect.centery - 8))
            surface.blit(sprite, sprite_rect)
            label = self.panel_small_font.render(piece.upper(), True, self.theme.promotion_text)
            surface.blit(label, label.get_rect(center=(rect.centerx, rect.bottom - 14)))

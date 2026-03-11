from __future__ import annotations

from dataclasses import dataclass
from math import sin

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
        engine_lines: list[str],
        review_badge: str | None,
        captured_by_white: list[str],
        captured_by_black: list[str],
        move_rows: list[str],
        move_scroll_offset: int,
        flipped: bool,
        last_move: Move | None,
        game_over_message: str | None,
        promotion_overlay: PromotionOverlayState | None,
        animation_phase: float,
    ) -> None:
        self._draw_gradient_background(surface)
        self._draw_orbs(surface, animation_phase)
        layout = BoardLayout(*self.theme.board_origin, self.theme.square_size, flipped)
        self._draw_board_frame(surface, animation_phase)
        self._draw_status_panel(surface, status_text)
        self._draw_side_panel(
            surface,
            detail_lines,
            engine_lines,
            review_badge,
            captured_by_white,
            captured_by_black,
            move_rows,
            move_scroll_offset,
            animation_phase,
        )
        self._draw_board(surface, layout)
        self._draw_last_move(surface, layout, last_move)
        self._draw_hover_square(surface, layout, input_state.hover_square)
        self._draw_selected_square(surface, layout, input_state.selected_square)
        self._draw_legal_moves(surface, layout, input_state.legal_moves)
        self._draw_coordinates(surface, layout)
        self._draw_pieces(surface, board, layout, input_state)
        self._draw_dragged_piece(surface, board, input_state, animation_phase)
        self._draw_game_over_overlay(surface, game_over_message, animation_phase)
        self._draw_promotion_overlay(surface, promotion_overlay, animation_phase)

    def _draw_gradient_background(self, surface: pygame.Surface) -> None:
        for y in range(self.theme.window_height):
            ratio = y / max(1, self.theme.window_height - 1)
            color = tuple(
                int(self.theme.background[index] * (1.0 - ratio) + self.theme.background_alt[index] * ratio)
                for index in range(3)
            )
            pygame.draw.line(surface, color, (0, y), (self.theme.window_width, y))

    def _draw_orbs(self, surface: pygame.Surface, animation_phase: float) -> None:
        self._draw_orb(surface, (132, 112), 180, self.theme.orb_primary, animation_phase * 0.9)
        self._draw_orb(surface, (842, 132), 150, self.theme.orb_secondary, animation_phase * 1.1)
        self._draw_orb(surface, (864, 628), 220, self.theme.orb_tertiary, animation_phase * 0.7)

    def _draw_orb(
        self,
        surface: pygame.Surface,
        center: tuple[int, int],
        radius: int,
        color: tuple[int, int, int, int],
        phase: float,
    ) -> None:
        orb = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        alpha = max(0, min(255, int(color[3] + 10 * sin(phase))))
        pygame.draw.circle(orb, (color[0], color[1], color[2], alpha), (radius, radius), radius)
        offset_y = int(6 * sin(phase))
        surface.blit(orb, (center[0] - radius, center[1] - radius + offset_y))

    def _draw_glass_panel(self, surface: pygame.Surface, rect: pygame.Rect, radius: int = 20, strong: bool = False) -> None:
        shadow = pygame.Surface((rect.width + 20, rect.height + 20), pygame.SRCALPHA)
        pygame.draw.rect(shadow, self.theme.glass_shadow, shadow.get_rect(), border_radius=radius + 8)
        surface.blit(shadow, (rect.x - 5, rect.y + 10))

        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        fill = self.theme.glass_fill_strong if strong else self.theme.glass_fill
        pygame.draw.rect(panel, fill, panel.get_rect(), border_radius=radius)
        pygame.draw.rect(panel, self.theme.glass_border, panel.get_rect(), width=2, border_radius=radius)
        shine = pygame.Rect(8, 8, rect.width - 16, max(18, rect.height // 6))
        pygame.draw.rect(panel, self.theme.glass_highlight, shine, border_radius=radius)
        surface.blit(panel, rect.topleft)

    def _draw_board_frame(self, surface: pygame.Surface, animation_phase: float) -> None:
        frame = pygame.Rect(self.theme.board_origin[0] - 10, self.theme.board_origin[1] - 10, self.theme.board_size + 20, self.theme.board_size + 20)
        self._draw_glass_panel(surface, frame, radius=30)
        outline = pygame.Surface(frame.size, pygame.SRCALPHA)
        pygame.draw.rect(outline, self.theme.board_frame, outline.get_rect(), width=2, border_radius=30)
        glow_alpha = 18 + int(12 * (sin(animation_phase * 1.7) + 1.0))
        pygame.draw.rect(outline, (255, 255, 255, glow_alpha), outline.get_rect().inflate(-10, -10), width=1, border_radius=26)
        surface.blit(outline, frame.topleft)

    def _draw_status_panel(self, surface: pygame.Surface, status_text: str) -> None:
        rect = pygame.Rect(18, self.theme.window_height - self.theme.status_height - 8, self.theme.window_width - 36, self.theme.status_height - 8)
        self._draw_glass_panel(surface, rect, radius=24, strong=True)
        status_surface = self.status_font.render(status_text, True, self.theme.status_text)
        surface.blit(status_surface, (rect.x + 20, rect.y + 22))

    def _draw_side_panel(
        self,
        surface: pygame.Surface,
        detail_lines: list[str],
        engine_lines: list[str],
        review_badge: str | None,
        captured_by_white: list[str],
        captured_by_black: list[str],
        move_rows: list[str],
        move_scroll_offset: int,
        animation_phase: float,
    ) -> None:
        rect = pygame.Rect(self.theme.side_panel_rect)
        self._draw_glass_panel(surface, rect, radius=28, strong=True)

        title = self.panel_title_font.render("Match", True, self.theme.heading_text)
        surface.blit(title, (rect.x + 20, rect.y + 18))

        for index, line in enumerate(detail_lines):
            body = self.panel_body_font.render(line, True, self.theme.muted_text)
            surface.blit(body, (rect.x + 20, rect.y + 76 + index * 30))

        engine_rect = pygame.Rect(rect.x + 16, rect.y + 206, rect.width - 32, 96)
        self._draw_engine_hud(surface, engine_rect, engine_lines, animation_phase)

        if review_badge is not None:
            self._draw_review_badge(surface, pygame.Rect(rect.x + 20, rect.y + 176, 158, 28), review_badge)

        capture_y = rect.y + 320
        heading = self.panel_title_font.render("Captures", True, self.theme.heading_text)
        surface.blit(heading, (rect.x + 20, capture_y))
        self._draw_capture_row(surface, rect.x + 20, capture_y + 44, "White", captured_by_white)
        self._draw_capture_row(surface, rect.x + 20, capture_y + 100, "Black", captured_by_black)

        moves_y = rect.y + 446
        moves_heading = self.panel_title_font.render("Moves", True, self.theme.heading_text)
        surface.blit(moves_heading, (rect.x + 20, moves_y))
        move_area = pygame.Rect(rect.x + 16, moves_y + 40, rect.width - 32, 76)
        self._draw_move_history(surface, move_area, move_rows, move_scroll_offset)

        shortcut_y = rect.bottom - 88
        controls = self.panel_title_font.render("Controls", True, self.theme.heading_text)
        surface.blit(controls, (rect.x + 20, shortcut_y))
        shortcuts = ["Esc Quit   M Menu", "R Reset   U Undo", "F Flip   T Theme"]
        for index, label in enumerate(shortcuts):
            line = self.panel_small_font.render(label, True, self.theme.muted_text)
            surface.blit(line, (rect.x + 20, shortcut_y + 36 + index * 18))

    def _draw_engine_hud(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        engine_lines: list[str],
        animation_phase: float,
    ) -> None:
        self._draw_glass_panel(surface, rect, radius=18)
        title = self.panel_title_font.render("Engine", True, self.theme.heading_text)
        surface.blit(title, (rect.x + 14, rect.y + 8))
        pulse_width = 8 + int(10 * (sin(animation_phase * 2.4) + 1.0))
        pygame.draw.ellipse(surface, self.theme.side_panel_accent, pygame.Rect(rect.right - pulse_width - 16, rect.y + 18, pulse_width, 10))
        for index, line in enumerate(engine_lines[:4]):
            text = self.panel_small_font.render(line, True, self.theme.muted_text)
            surface.blit(text, (rect.x + 16, rect.y + 40 + index * 14))

    def _draw_review_badge(self, surface: pygame.Surface, rect: pygame.Rect, review_badge: str) -> None:
        color_map = {
            "best": (92, 225, 156),
            "brilliant": (112, 224, 255),
            "great": (145, 232, 178),
            "good": (187, 225, 128),
            "inaccuracy": (255, 205, 107),
            "mistake": (255, 158, 96),
            "blunder": (255, 112, 112),
        }
        badge_fill = color_map.get(review_badge.lower(), self.theme.side_panel_accent)
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (*badge_fill, 72), panel.get_rect(), border_radius=14)
        pygame.draw.rect(panel, self.theme.glass_border, panel.get_rect(), width=1, border_radius=14)
        surface.blit(panel, rect.topleft)
        label = self.panel_small_font.render(f"Review: {review_badge.title()}", True, self.theme.heading_text)
        surface.blit(label, label.get_rect(center=rect.center))

    def _draw_capture_row(self, surface: pygame.Surface, x: int, y: int, label: str, pieces: list[str]) -> None:
        text = self.panel_small_font.render(label, True, self.theme.heading_text)
        surface.blit(text, (x, y))
        for index, piece in enumerate(pieces[:8]):
            capsule = pygame.Rect(x + 54 + index * 28, y - 8, 26, 26)
            capsule_surface = pygame.Surface(capsule.size, pygame.SRCALPHA)
            pygame.draw.rect(capsule_surface, self.theme.glass_fill, capsule_surface.get_rect(), border_radius=10)
            pygame.draw.rect(capsule_surface, self.theme.glass_border, capsule_surface.get_rect(), width=1, border_radius=10)
            surface.blit(capsule_surface, capsule.topleft)
            sprite = self.sprites.preview[piece]
            surface.blit(sprite, (capsule.x - 19, capsule.y - 19))

    def _draw_move_history(self, surface: pygame.Surface, area: pygame.Rect, move_rows: list[str], move_scroll_offset: int) -> None:
        self._draw_glass_panel(surface, area, radius=18)
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
            pygame.draw.rect(surface, self.theme.glass_fill, track, border_radius=4)
            thumb_height = max(18, int(track.height * (visible_count / len(rows))))
            scroll_ratio = start_index / max_offset if max_offset else 0.0
            thumb_y = track.y + int((track.height - thumb_height) * scroll_ratio)
            thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_height)
            pygame.draw.rect(surface, self.theme.side_panel_accent, thumb, border_radius=4)

    def _draw_board(self, surface: pygame.Surface, layout: BoardLayout) -> None:
        board_surface = pygame.Surface((self.theme.board_size, self.theme.board_size), pygame.SRCALPHA)
        for square in range(64):
            rect = layout.square_rect(square)
            local_rect = pygame.Rect(rect.x - layout.origin_x, rect.y - layout.origin_y, rect.width, rect.height)
            row = square // 8
            col = square % 8
            color = self.theme.light_square if (row + col) % 2 == 0 else self.theme.dark_square
            pygame.draw.rect(board_surface, color, local_rect)
        glaze = pygame.Surface((self.theme.board_size, self.theme.board_size), pygame.SRCALPHA)
        pygame.draw.rect(glaze, self.theme.glass_fill, glaze.get_rect(), border_radius=24)
        board_surface.blit(glaze, (0, 0))
        surface.blit(board_surface, self.theme.board_origin)

    def _draw_last_move(self, surface: pygame.Surface, layout: BoardLayout, last_move: Move | None) -> None:
        if last_move is None:
            return
        overlay = pygame.Surface((self.theme.square_size, self.theme.square_size), pygame.SRCALPHA)
        overlay.fill(self.theme.last_move_fill)
        for square in (last_move.from_square, last_move.to_square):
            surface.blit(overlay, layout.square_rect(square).topleft)

    def _draw_hover_square(self, surface: pygame.Surface, layout: BoardLayout, square: int | None) -> None:
        if square is None:
            return
        rect = layout.square_rect(square)
        hover = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(hover, (255, 255, 255, 26), hover.get_rect(), border_radius=12)
        surface.blit(hover, rect.topleft)

    def _draw_selected_square(self, surface: pygame.Surface, layout: BoardLayout, square: int | None) -> None:
        if square is None:
            return
        rect = layout.square_rect(square)
        glow = pygame.Surface((rect.width + 18, rect.height + 18), pygame.SRCALPHA)
        pygame.draw.rect(glow, (*self.theme.selected_outline, 55), glow.get_rect(), border_radius=16)
        surface.blit(glow, (rect.x - 9, rect.y - 9))
        pygame.draw.rect(surface, self.theme.selected_outline, rect.inflate(-6, -6), width=self.theme.selected_outline_width, border_radius=12)

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

    def _draw_dragged_piece(
        self,
        surface: pygame.Surface,
        board: Board,
        input_state: InputState,
        animation_phase: float,
    ) -> None:
        if not input_state.is_dragging or input_state.drag_origin is None or input_state.drag_position is None:
            return
        piece = board.piece_at(input_state.drag_origin)
        if piece == EMPTY:
            return
        sprite = self.sprites.dragged[piece]
        shadow = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        shadow.fill(self.theme.drag_shadow)
        rect = sprite.get_rect(center=input_state.drag_position)
        float_offset = int(3 * sin(animation_phase * 8.0))
        glow = pygame.Surface((rect.width + 24, rect.height + 24), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*self.theme.side_panel_accent, 42), glow.get_rect())
        surface.blit(glow, (rect.x - 12, rect.y - 12 + float_offset))
        surface.blit(shadow, rect.move(4, 7 + float_offset))
        surface.blit(sprite, rect)

    def _draw_game_over_overlay(
        self,
        surface: pygame.Surface,
        game_over_message: str | None,
        animation_phase: float,
    ) -> None:
        if game_over_message is None:
            return
        overlay = pygame.Surface((self.theme.board_size, self.theme.board_size), pygame.SRCALPHA)
        overlay.fill(self.theme.overlay_fill)
        surface.blit(overlay, self.theme.board_origin)
        banner = pygame.Rect(0, 0, 360, 124)
        board_x, board_y = self.theme.board_origin
        banner.center = (board_x + self.theme.board_size // 2, board_y + self.theme.board_size // 2 + int(4 * sin(animation_phase * 1.8)))
        self._draw_glass_panel(surface, banner, radius=24, strong=True)
        title = self.panel_title_font.render("Game Over", True, self.theme.heading_text)
        message = self.panel_body_font.render(game_over_message, True, self.theme.heading_text)
        hint = self.coord_font.render("Press R to restart or M for menu", True, self.theme.muted_text)
        surface.blit(title, title.get_rect(center=(banner.centerx, banner.y + 32)))
        surface.blit(message, message.get_rect(center=(banner.centerx, banner.y + 68)))
        surface.blit(hint, hint.get_rect(center=(banner.centerx, banner.y + 100)))

    def _draw_promotion_overlay(
        self,
        surface: pygame.Surface,
        promotion_overlay: PromotionOverlayState | None,
        animation_phase: float,
    ) -> None:
        if promotion_overlay is None:
            return
        overlay = pygame.Surface((self.theme.board_size, self.theme.board_size), pygame.SRCALPHA)
        overlay.fill(self.theme.overlay_fill)
        surface.blit(overlay, self.theme.board_origin)
        title_rect = pygame.Rect(self.theme.board_origin[0] + 156, self.theme.board_origin[1] + 210 + int(3 * sin(animation_phase * 1.6)), 328, 44)
        title = self.panel_body_font.render("Choose promotion", True, self.theme.heading_text)
        surface.blit(title, title.get_rect(center=title_rect.center))
        for move, rect in zip(promotion_overlay.moves, promotion_option_rects(self.theme), strict=True):
            self._draw_glass_panel(surface, rect, radius=18, strong=True)
            piece = move.promotion if move.promotion is not None else move.piece
            sprite = self.sprites.preview[piece]
            sprite_rect = sprite.get_rect(center=(rect.centerx, rect.centery - 8))
            surface.blit(sprite, sprite_rect)
            label = self.panel_small_font.render(piece.upper(), True, self.theme.promotion_text)
            surface.blit(label, label.get_rect(center=(rect.centerx, rect.bottom - 14)))

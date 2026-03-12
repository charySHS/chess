from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame

from src.ui.apple import blit_fit_text, draw_glass_button, draw_glass_panel, draw_glass_pill, draw_gradient_backdrop, draw_orb
from src.ui.theme import Theme


@dataclass(frozen=True)
class MenuAction:
    label: str
    callback: Callable[[], None] | None
    description: str
    enabled: bool = True


@dataclass(frozen=True)
class UpdateItem:
    section: str
    title: str
    detail: str
    body: tuple[str, ...]


def _lerp(current: float, target: float, speed: float) -> float:
    return current + (target - current) * speed


class MenuScene:
    def __init__(
        self,
        screen: pygame.Surface,
        theme: Theme,
        start_local_game: Callable[[], None],
        start_engine_game: Callable[[], None],
        cycle_theme: Callable[[], None],
        request_quit: Callable[[], None],
    ) -> None:
        self.screen = screen
        self.theme = theme
        self.start_local_game = start_local_game
        self.start_engine_game = start_engine_game
        self.cycle_theme = cycle_theme
        self.request_quit = request_quit
        self.button_rects: list[pygame.Rect] = []
        self.actions: list[MenuAction] = []
        self.action_hover: list[float] = []
        self.update_items: list[UpdateItem] = []
        self.update_rects: list[tuple[pygame.Rect, int]] = []
        self.log_scroll_area = pygame.Rect(0, 0, 0, 0)
        self.log_scroll_offset = 0.0
        self.log_content_height = 0
        self.detail_scroll_offset = 0.0
        self.detail_scroll_area = pygame.Rect(0, 0, 0, 0)
        self.selected_update_index: int | None = None
        self.entered_at_ms = pygame.time.get_ticks()
        self._build_fonts()
        self._build_actions()
        self._build_update_items()

    def activate(self) -> None:
        self.entered_at_ms = pygame.time.get_ticks()

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self._build_fonts()

    def set_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen

    def _build_fonts(self) -> None:
        self.title_font = pygame.font.SysFont("segoeui", 68, bold=True)
        self.kicker_font = pygame.font.SysFont("trebuchetms", 18, bold=True)
        self.subtitle_font = pygame.font.SysFont("segoeui", 23)
        self.button_font = pygame.font.SysFont("segoeui", 24, bold=True)
        self.small_font = pygame.font.SysFont("trebuchetms", 17)
        self.meta_font = pygame.font.SysFont("trebuchetms", 15, bold=True)

    def _build_actions(self) -> None:
        self.actions = [
            MenuAction("Play Local Game", self.start_local_game, "Pass-and-play from the same board."),
            MenuAction("Play vs Engine", self.start_engine_game, "Jump into a quick solo session against the local engine."),
            MenuAction("Change Theme", self.cycle_theme, "Cycle the active appearance set."),
            MenuAction("Quit", self.request_quit, "Close the desktop app."),
        ]
        self.action_hover = [0.0 for _ in self.actions]

    def _build_update_items(self) -> None:
        self.update_items = [
            UpdateItem(
                "Latest",
                "Apple-style home refresh",
                "Cleaner hero layout, softer glass surfaces, and a more focused landing page.",
                (
                    "The home view now avoids the oversized boxed dashboard look and leans closer to the reference with lighter floating groups.",
                    "We reduced visual clutter around the hero area so the page reads as content first and chrome second.",
                    "The result is calmer and more layered, especially in the right-hand update stack.",
                ),
            ),
            UpdateItem(
                "Latest",
                "Hover-driven actions",
                "Menu options now grow on focus and reveal their supporting text only when active.",
                (
                    "Each action now behaves more like an interactive control cluster instead of a static menu row.",
                    "Descriptions stay hidden until intent is clear, which keeps the page lighter at rest.",
                    "Hover scaling is restrained so it feels responsive without becoming gamey.",
                ),
            ),
            UpdateItem(
                "Latest",
                "Scene transitions",
                "The home screen panels now ease into place instead of appearing all at once.",
                (
                    "We added a simple entrance animation so the homepage settles in rather than popping onto the screen.",
                    "This is meant to support the glass effect by making layers feel suspended and physical.",
                    "The same transition pattern can be reused later for menu-to-game routing.",
                ),
            ),
            UpdateItem(
                "Planned",
                "Board polish pass",
                "Tone down square contrast and align move highlights with the same calmer visual language.",
                (
                    "The board still carries more contrast than the menu reference.",
                    "Next pass should soften the square colors, selection outlines, and move indicators.",
                    "That will make gameplay feel like part of the same system instead of a separate skin.",
                ),
            ),
            UpdateItem(
                "Planned",
                "Richer engine panel",
                "Expose better eval context and deeper review labels in the side HUD.",
                (
                    "The current engine area is readable but still shallow.",
                    "We want room for better principal variation context, score framing, and review phrasing.",
                    "That should happen without turning the side panel into a developer-only readout.",
                ),
            ),
            UpdateItem(
                "Planned",
                "Session memory",
                "Keep recent menu selections and appearance choices between launches.",
                (
                    "Theme and preferred mode should persist so the app feels less stateless.",
                    "This also gives the home screen a stronger sense of continuity across sessions.",
                    "Once saved settings exist, the update log can point to what changed since your last run.",
                ),
            ),
        ]

    def update(self) -> None:
        mouse_pos = pygame.mouse.get_pos()
        for index, rect in enumerate(self.button_rects):
            target = 1.0 if rect.collidepoint(mouse_pos) else 0.0
            self.action_hover[index] = _lerp(self.action_hover[index], target, 0.22)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.request_quit()
            return

        if event.type == pygame.KEYDOWN:
            if self.selected_update_index is not None and event.key == pygame.K_ESCAPE:
                self.selected_update_index = None
                self.detail_scroll_offset = 0.0
                return
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_local_game()
            elif event.key == pygame.K_t:
                self.cycle_theme()
            elif event.key == pygame.K_ESCAPE:
                self.request_quit()
            return

        if event.type == pygame.MOUSEWHEEL:
            self._handle_mousewheel(event)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.selected_update_index is not None:
                if not self.detail_scroll_area.inflate(48, 72).collidepoint(event.pos):
                    self.selected_update_index = None
                    self.detail_scroll_offset = 0.0
                return
            for rect, update_index in self.update_rects:
                if rect.collidepoint(event.pos):
                    self.selected_update_index = update_index
                    self.detail_scroll_offset = 0.0
                    return
            for rect, action in zip(self.button_rects, self.actions, strict=True):
                if rect.collidepoint(event.pos) and action.enabled and action.callback is not None:
                    action.callback()
                    return

    def _handle_mousewheel(self, event: pygame.event.Event) -> None:
        if self.selected_update_index is not None and self.detail_scroll_area.collidepoint(pygame.mouse.get_pos()):
            max_offset = max(0.0, self.log_content_height - self.detail_scroll_area.height)
            self.detail_scroll_offset = max(0.0, min(self.detail_scroll_offset - event.y * 26, max_offset))
            return
        if not self.log_scroll_area.collidepoint(pygame.mouse.get_pos()):
            return
        max_offset = max(0.0, self.log_content_height - self.log_scroll_area.height)
        self.log_scroll_offset = max(0.0, min(self.log_scroll_offset - event.y * 26, max_offset))

    def draw(self) -> None:
        now_ms = pygame.time.get_ticks()
        phase = now_ms / 1000.0
        intro = min(1.0, (now_ms - self.entered_at_ms) / 650.0)
        eased_intro = 1.0 - (1.0 - intro) * (1.0 - intro)
        draw_gradient_backdrop(self.screen, self.theme, grid_spacing=64)
        self._draw_orbs(phase)
        self._draw_shell(phase, eased_intro)
        if self.selected_update_index is not None:
            self._draw_update_detail_modal()
        pygame.display.flip()

    def _draw_orbs(self, phase: float) -> None:
        width = self.theme.window_width
        height = self.theme.window_height
        draw_orb(self.screen, (int(width * 0.14), int(height * 0.15)), max(170, width // 5), self.theme.orb_primary, phase * 0.8)
        draw_orb(self.screen, (int(width * 0.78), int(height * 0.18)), max(132, width // 7), self.theme.orb_secondary, phase * 1.1)
        draw_orb(self.screen, (int(width * 0.82), int(height * 0.82)), max(200, width // 4), self.theme.orb_tertiary, phase * 0.7)

    def _draw_shell(self, phase: float, intro: float) -> None:
        padding = 56
        slide = int((1.0 - intro) * 34)
        card_rect = pygame.Rect(
            padding,
            padding + slide,
            self.theme.window_width - padding * 2,
            self.theme.window_height - padding * 2,
        )
        draw_glass_panel(self.screen, self.theme, card_rect, radius=32)

        blit_fit_text(
            self.screen,
            self.kicker_font,
            "HOME",
            self.theme.heading_text,
            pygame.Rect(card_rect.x + 42, card_rect.y + 40, 90, 18),
        )
        blit_fit_text(
            self.screen,
            self.title_font,
            "NewChess",
            self.theme.heading_text,
            pygame.Rect(card_rect.x + 42, card_rect.y + 78, card_rect.width - 84, 60),
        )
        blit_fit_text(
            self.screen,
            self.subtitle_font,
            "Smoother motion, focused actions, and a clearer sense of what is changing next.",
            self.theme.muted_text,
            pygame.Rect(card_rect.x + 44, card_rect.y + 146, card_rect.width - 88, 28),
        )

        badge_rect = pygame.Rect(card_rect.x + 42, card_rect.y + 198, 276, 34)
        draw_glass_pill(self.screen, self.theme, badge_rect)
        blit_fit_text(
            self.screen,
            self.small_font,
            f"{self.theme.name.title()} appearance  |  Press T",
            self.theme.heading_text,
            badge_rect.inflate(-12, -6),
            center=True,
        )

        actions_rect = pygame.Rect(card_rect.x + 34, card_rect.y + 260, 400, card_rect.height - 302)
        updates_rect = pygame.Rect(card_rect.x + 468, card_rect.y + 208, card_rect.width - 516, card_rect.height - 250)
        draw_glass_panel(self.screen, self.theme, actions_rect, radius=30)

        blit_fit_text(
            self.screen,
            self.subtitle_font,
            "Quick Start",
            self.theme.heading_text,
            pygame.Rect(actions_rect.x + 20, actions_rect.y + 18, actions_rect.width - 40, 24),
        )
        blit_fit_text(
            self.screen,
            self.kicker_font,
            "UPDATE STACK",
            self.theme.heading_text,
            pygame.Rect(updates_rect.x + 20, updates_rect.y + 6, updates_rect.width - 40, 18),
        )

        self._draw_action_buttons(actions_rect, phase)
        self._draw_updates_panel(updates_rect)

        footer_rect = pygame.Rect(card_rect.x + 42, card_rect.bottom - 34, card_rect.width - 84, 18)
        blit_fit_text(
            self.screen,
            self.small_font,
            "Enter starts local play. Mouse wheel scrolls the update log. F11 toggles fullscreen.",
            self.theme.subtle_text,
            footer_rect,
        )

    def _draw_action_buttons(self, actions_rect: pygame.Rect, phase: float) -> None:
        mouse_pos = pygame.mouse.get_pos()
        self.button_rects = []
        slot_height = 64
        start_y = actions_rect.y + 62
        for index, action in enumerate(self.actions):
            hover = self.action_hover[index]
            base_rect = pygame.Rect(actions_rect.x + 14, start_y + index * slot_height, actions_rect.width - 28, 52)
            grow_x = int(8 * hover)
            grow_y = int(10 * hover)
            rect = pygame.Rect(
                base_rect.x - grow_x // 2,
                base_rect.y - grow_y // 2,
                base_rect.width + grow_x,
                base_rect.height + grow_y,
            )
            self.button_rects.append(rect)
            draw_glass_button(
                self.screen,
                self.theme,
                rect,
                hovered=rect.collidepoint(mouse_pos) and action.enabled,
                enabled=action.enabled,
                phase=phase + index * 0.28,
                radius=22,
            )

            label_rect = pygame.Rect(rect.x + 16, rect.y + 10, rect.width - 32, 22)
            blit_fit_text(
                self.screen,
                self.button_font,
                action.label,
                self.theme.heading_text if action.enabled else (218, 224, 232),
                label_rect,
            )
            if hover > 0.08:
                desc_alpha = max(0, min(255, int(255 * hover)))
                desc_surface = pygame.Surface((rect.width - 32, 16), pygame.SRCALPHA)
                text = self.small_font.render(action.description, True, (*self.theme.subtle_text, desc_alpha))
                desc_surface.blit(text, (0, 0))
                self.screen.blit(desc_surface, (rect.x + 16, rect.y + 30))

    def _draw_updates_panel(self, updates_rect: pygame.Rect) -> None:
        header_pill = pygame.Rect(updates_rect.right - 120, updates_rect.y - 2, 102, 24)
        draw_glass_pill(self.screen, self.theme, header_pill, radius=12)
        blit_fit_text(self.screen, self.meta_font, "Tap For More", self.theme.heading_text, header_pill.inflate(-8, -6), center=True)

        scroll_rect = pygame.Rect(updates_rect.x, updates_rect.y + 26, updates_rect.width, updates_rect.height - 26)
        self.log_scroll_area = scroll_rect
        self._draw_update_rows(scroll_rect)

    def _draw_update_rows(self, scroll_rect: pygame.Rect) -> None:
        self.update_rects = []
        row_height = 114
        content_height = max(scroll_rect.height, len(self.update_items) * row_height)
        content_surface = pygame.Surface((scroll_rect.width - 10, content_height), pygame.SRCALPHA)
        y = 0
        for index, item in enumerate(self.update_items):
            row_rect = pygame.Rect(0, y, content_surface.get_width(), row_height - 18)
            draw_glass_panel(content_surface, self.theme, row_rect, radius=24)
            tag_rect = pygame.Rect(row_rect.x + 12, row_rect.y + 10, 74 if item.section == "Latest" else 82, 22)
            draw_glass_pill(content_surface, self.theme, tag_rect, radius=12)
            blit_fit_text(content_surface, self.meta_font, item.section, self.theme.heading_text, tag_rect.inflate(-8, -6), center=True)
            blit_fit_text(content_surface, self.button_font, item.title, self.theme.heading_text, pygame.Rect(row_rect.x + 14, row_rect.y + 38, row_rect.width - 28, 20))
            blit_fit_text(content_surface, self.small_font, item.detail, self.theme.subtle_text, pygame.Rect(row_rect.x + 14, row_rect.y + 64, row_rect.width - 56, 16))
            draw_glass_pill(content_surface, self.theme, pygame.Rect(row_rect.right - 102, row_rect.y + 72, 88, 24), radius=12)
            blit_fit_text(content_surface, self.meta_font, "Open Detail", self.theme.heading_text, pygame.Rect(row_rect.right - 98, row_rect.y + 77, 80, 14), center=True)
            self.update_rects.append((pygame.Rect(scroll_rect.x, scroll_rect.y + y - int(self.log_scroll_offset), row_rect.width, row_rect.height), index))
            y += row_height

        self.log_content_height = y
        max_offset = max(0.0, self.log_content_height - scroll_rect.height)
        self.log_scroll_offset = max(0.0, min(self.log_scroll_offset, max_offset))
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(scroll_rect)
        self.screen.blit(content_surface, (scroll_rect.x, scroll_rect.y - int(self.log_scroll_offset)))
        self.screen.set_clip(previous_clip)

        if max_offset > 0:
            track = pygame.Rect(scroll_rect.right - 4, scroll_rect.y, 4, scroll_rect.height)
            pygame.draw.rect(self.screen, self.theme.glass_fill_soft, track, border_radius=4)
            thumb_height = max(28, int(track.height * (scroll_rect.height / self.log_content_height)))
            thumb_y = track.y + int((track.height - thumb_height) * (self.log_scroll_offset / max_offset))
            pygame.draw.rect(self.screen, self.theme.side_panel_accent, pygame.Rect(track.x, thumb_y, track.width, thumb_height), border_radius=4)

    def _draw_update_detail_modal(self) -> None:
        selected = self.update_items[self.selected_update_index]
        overlay = pygame.Surface((self.theme.window_width, self.theme.window_height), pygame.SRCALPHA)
        overlay.fill((24, 31, 45, 112))
        self.screen.blit(overlay, (0, 0))

        rect = pygame.Rect(
            self.theme.window_width // 2 - 240,
            self.theme.window_height // 2 - 220,
            480,
            440,
        )
        draw_glass_panel(self.screen, self.theme, rect, radius=30, strong=True)
        tag_rect = pygame.Rect(rect.x + 22, rect.y + 20, 84 if selected.section == "Latest" else 92, 24)
        draw_glass_pill(self.screen, self.theme, tag_rect, radius=12)
        blit_fit_text(self.screen, self.meta_font, selected.section, self.theme.heading_text, tag_rect.inflate(-8, -6), center=True)
        close_rect = pygame.Rect(rect.right - 48, rect.y + 18, 28, 28)
        draw_glass_pill(self.screen, self.theme, close_rect, radius=14)
        blit_fit_text(self.screen, self.meta_font, "X", self.theme.heading_text, close_rect.inflate(-6, -6), center=True)

        blit_fit_text(self.screen, self.subtitle_font, selected.title, self.theme.heading_text, pygame.Rect(rect.x + 22, rect.y + 58, rect.width - 44, 24))
        blit_fit_text(self.screen, self.small_font, selected.detail, self.theme.subtle_text, pygame.Rect(rect.x + 22, rect.y + 88, rect.width - 44, 18))

        body_rect = pygame.Rect(rect.x + 22, rect.y + 126, rect.width - 44, rect.height - 148)
        self.detail_scroll_area = body_rect
        content_height = max(body_rect.height, len(selected.body) * 86)
        content = pygame.Surface((body_rect.width - 10, content_height), pygame.SRCALPHA)
        y = 0
        for paragraph in selected.body:
            block = pygame.Rect(0, y, content.get_width(), 72)
            draw_glass_pill(content, self.theme, block, radius=20)
            used_height = self._blit_wrapped_text(
                content,
                self.small_font,
                paragraph,
                self.theme.muted_text,
                pygame.Rect(block.x + 14, block.y + 14, block.width - 28, block.height - 20),
                line_height=18,
            )
            y += max(86, used_height + 34)
        self.log_content_height = y
        max_offset = max(0.0, self.log_content_height - body_rect.height)
        self.detail_scroll_offset = max(0.0, min(self.detail_scroll_offset, max_offset))
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(body_rect)
        self.screen.blit(content, (body_rect.x, body_rect.y - int(self.detail_scroll_offset)))
        self.screen.set_clip(previous_clip)

    def _blit_wrapped_text(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        color: tuple[int, int, int],
        rect: pygame.Rect,
        *,
        line_height: int,
    ) -> int:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if font.size(candidate)[0] <= rect.width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        for index, line in enumerate(lines):
            if rect.y + index * line_height > rect.bottom - line_height:
                break
            rendered = font.render(line, True, color)
            surface.blit(rendered, (rect.x, rect.y + index * line_height))
        return len(lines) * line_height

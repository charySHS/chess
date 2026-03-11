from __future__ import annotations

from dataclasses import dataclass
from math import sin
from typing import Callable

import pygame

from src.ui.theme import Theme


@dataclass(frozen=True)
class MenuAction:
    label: str
    callback: Callable[[], None] | None
    description: str
    enabled: bool = True


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
        self._build_fonts()
        self._build_actions()

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self._build_fonts()

    def _build_fonts(self) -> None:
        self.title_font = pygame.font.SysFont("georgia", 60, bold=True)
        self.subtitle_font = pygame.font.SysFont("georgia", 24)
        self.button_font = pygame.font.SysFont("arial", 25, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18)

    def _build_actions(self) -> None:
        self.actions = [
            MenuAction("Play Local Game", self.start_local_game, "Pass-and-play on one board"),
            MenuAction("Play vs Engine", self.start_engine_game, "Human as White against the local engine"),
            MenuAction("Change Theme", self.cycle_theme, "Cycle between glass theme variants"),
            MenuAction("Quit", self.request_quit, "Exit the application"),
        ]

    def update(self) -> None:
        return

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.request_quit()
            return

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_local_game()
            elif event.key == pygame.K_t:
                self.cycle_theme()
            elif event.key == pygame.K_ESCAPE:
                self.request_quit()
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action in zip(self.button_rects, self.actions, strict=True):
                if rect.collidepoint(event.pos) and action.enabled and action.callback is not None:
                    action.callback()
                    return

    def draw(self) -> None:
        phase = pygame.time.get_ticks() / 1000.0
        self._draw_gradient_background()
        self._draw_orbs(phase)
        self._draw_shell(phase)
        pygame.display.flip()

    def _draw_gradient_background(self) -> None:
        for y in range(self.theme.window_height):
            ratio = y / max(1, self.theme.window_height - 1)
            color = tuple(
                int(self.theme.background[index] * (1.0 - ratio) + self.theme.background_alt[index] * ratio)
                for index in range(3)
            )
            pygame.draw.line(self.screen, color, (0, y), (self.theme.window_width, y))

    def _draw_orbs(self, phase: float) -> None:
        self._draw_orb((152, 120), 210, self.theme.orb_primary, phase * 0.8)
        self._draw_orb((762, 160), 160, self.theme.orb_secondary, phase * 1.1)
        self._draw_orb((818, 612), 240, self.theme.orb_tertiary, phase * 0.7)

    def _draw_orb(self, center: tuple[int, int], radius: int, color: tuple[int, int, int, int], phase: float) -> None:
        orb = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        alpha = max(0, min(255, int(color[3] + 10 * sin(phase))))
        pygame.draw.circle(orb, (color[0], color[1], color[2], alpha), (radius, radius), radius)
        self.screen.blit(orb, (center[0] - radius, center[1] - radius + int(6 * sin(phase))))

    def _draw_shell(self, phase: float) -> None:
        card_rect = pygame.Rect(74, 76, self.theme.window_width - 148, self.theme.window_height - 152)
        self._draw_glass_panel(card_rect, radius=30)

        title = self.title_font.render("NewChess", True, self.theme.heading_text)
        subtitle = self.subtitle_font.render(
            "A crisp board UI with a liquid glass shell and engine foundations under it.",
            True,
            self.theme.muted_text,
        )
        self.screen.blit(title, (card_rect.x + 42, card_rect.y + 38))
        self.screen.blit(subtitle, (card_rect.x + 44, card_rect.y + 110))

        badge_rect = pygame.Rect(card_rect.x + 44, card_rect.y + 152, 246, 34)
        self._draw_glass_pill(badge_rect)
        badge = self.small_font.render(f"Theme {self.theme.name.title()}   |   Press T", True, self.theme.heading_text)
        self.screen.blit(badge, badge.get_rect(center=badge_rect.center))

        self.button_rects = []
        mouse_pos = pygame.mouse.get_pos()
        start_y = card_rect.y + 224
        for index, action in enumerate(self.actions):
            rect = pygame.Rect(card_rect.x + 44, start_y + index * 88, 350, 66)
            self.button_rects.append(rect)
            self._draw_glass_button(
                rect,
                hovered=rect.collidepoint(mouse_pos) and action.enabled,
                enabled=action.enabled,
                phase=phase + index * 0.3,
            )

            title_text = self.button_font.render(action.label, True, self.theme.heading_text if action.enabled else (218, 224, 232))
            desc_text = self.small_font.render(action.description, True, self.theme.muted_text if action.enabled else (196, 204, 212))
            self.screen.blit(title_text, (rect.x + 18, rect.y + 11))
            self.screen.blit(desc_text, (rect.x + 18, rect.y + 40))

        insight_rect = pygame.Rect(card_rect.x + 440, card_rect.y + 212, 364, 314)
        self._draw_glass_panel(insight_rect, radius=24)
        section = self.subtitle_font.render("Current Focus", True, self.theme.heading_text)
        self.screen.blit(section, (insight_rect.x + 24, insight_rect.y + 20))
        notes = [
            "Liquid glass menu and in-game panels",
            "Promotion picker and bounded move history",
            "Stockfish bridge, NN training scaffold, iterative search",
            "Engine play slot reserved for the next integration step",
        ]
        for index, note in enumerate(notes):
            dot_rect = pygame.Rect(insight_rect.x + 26, insight_rect.y + 74 + index * 54, 10, 10)
            pygame.draw.ellipse(self.screen, self.theme.side_panel_accent, dot_rect)
            text = self.small_font.render(note, True, self.theme.muted_text)
            self.screen.blit(text, (insight_rect.x + 48, insight_rect.y + 68 + index * 54))

        footer = self.small_font.render("Enter starts local play. Esc quits.", True, self.theme.muted_text)
        self.screen.blit(footer, (card_rect.x + 44, card_rect.bottom - 40))

    def _draw_glass_panel(self, rect: pygame.Rect, radius: int) -> None:
        shadow = pygame.Surface((rect.width + 22, rect.height + 22), pygame.SRCALPHA)
        pygame.draw.rect(shadow, self.theme.glass_shadow, shadow.get_rect(), border_radius=radius + 10)
        self.screen.blit(shadow, (rect.x - 6, rect.y + 12))

        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, self.theme.glass_fill, panel.get_rect(), border_radius=radius)
        pygame.draw.rect(panel, self.theme.glass_border, panel.get_rect(), width=2, border_radius=radius)
        highlight = pygame.Rect(8, 8, rect.width - 16, max(20, rect.height // 5))
        pygame.draw.rect(panel, self.theme.glass_highlight, highlight, border_radius=radius)
        self.screen.blit(panel, rect.topleft)

    def _draw_glass_pill(self, rect: pygame.Rect) -> None:
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, self.theme.glass_fill_strong, panel.get_rect(), border_radius=18)
        pygame.draw.rect(panel, self.theme.glass_border, panel.get_rect(), width=1, border_radius=18)
        self.screen.blit(panel, rect.topleft)

    def _draw_glass_button(self, rect: pygame.Rect, hovered: bool, enabled: bool, phase: float) -> None:
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        fill = self.theme.glass_fill_strong if enabled else (255, 255, 255, 28)
        if hovered:
            fill = (fill[0], fill[1], fill[2], min(fill[3] + 24, 160))
        pygame.draw.rect(panel, fill, panel.get_rect(), border_radius=22)
        pygame.draw.rect(panel, self.theme.glass_border, panel.get_rect(), width=2, border_radius=22)
        highlight = pygame.Rect(6, 6, rect.width - 12, 18)
        pulse_alpha = max(0, min(255, int(self.theme.glass_highlight[3] + 14 * sin(phase * 2.2))))
        pygame.draw.rect(panel, (255, 255, 255, pulse_alpha), highlight, border_radius=16)
        self.screen.blit(panel, rect.topleft)

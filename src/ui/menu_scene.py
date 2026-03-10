from __future__ import annotations

from dataclasses import dataclass
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
        cycle_theme: Callable[[], None],
        request_quit: Callable[[], None],
    ) -> None:
        self.screen = screen
        self.theme = theme
        self.start_local_game = start_local_game
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
        self.title_font = pygame.font.SysFont("georgia", 54, bold=True)
        self.subtitle_font = pygame.font.SysFont("georgia", 22)
        self.button_font = pygame.font.SysFont("arial", 25, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18)

    def _build_actions(self) -> None:
        self.actions = [
            MenuAction("Play Local Game", self.start_local_game, "Human vs human on one board"),
            MenuAction("Play vs Engine", None, "Reserved for the NN engine path", enabled=False),
            MenuAction("Change Theme", self.cycle_theme, "Rotate the active board and panel theme"),
            MenuAction("Quit", self.request_quit, "Exit the application"),
        ]

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
        self.screen.fill(self.theme.background)
        self._draw_backdrop()
        self._draw_card()
        pygame.display.flip()

    def _draw_backdrop(self) -> None:
        pygame.draw.circle(self.screen, self.theme.side_panel_accent, (150, 120), 170)
        pygame.draw.circle(self.screen, self.theme.dark_square, (720, 560), 230)
        pygame.draw.circle(self.screen, self.theme.light_square, (820, 140), 130)

    def _draw_card(self) -> None:
        card_rect = pygame.Rect(96, 92, self.theme.window_width - 192, self.theme.window_height - 184)
        shadow_rect = card_rect.move(0, 10)
        shadow = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 55))
        self.screen.blit(shadow, shadow_rect.topleft)
        pygame.draw.rect(self.screen, self.theme.win_banner, card_rect, border_radius=20)
        pygame.draw.rect(self.screen, self.theme.side_panel_accent, card_rect, width=3, border_radius=20)

        title = self.title_font.render("NewChess", True, self.theme.win_banner_text)
        subtitle = self.subtitle_font.render(
            "Board UI, analysis hooks, and the first NN training foundation.",
            True,
            self.theme.win_banner_text,
        )
        self.screen.blit(title, (card_rect.x + 42, card_rect.y + 36))
        self.screen.blit(subtitle, (card_rect.x + 44, card_rect.y + 102))

        theme_text = self.small_font.render(f"Theme: {self.theme.name.title()}  |  T cycles themes", True, self.theme.win_banner_text)
        self.screen.blit(theme_text, (card_rect.x + 46, card_rect.y + 150))

        self.button_rects = []
        start_y = card_rect.y + 210
        mouse_pos = pygame.mouse.get_pos()
        for index, action in enumerate(self.actions):
            rect = pygame.Rect(card_rect.x + 46, start_y + index * 86, 330, 62)
            self.button_rects.append(rect)
            hovered = rect.collidepoint(mouse_pos) and action.enabled
            fill = self.theme.side_panel_background if action.enabled else (110, 110, 110)
            if hovered:
                fill = tuple(min(channel + 18, 255) for channel in fill)
            pygame.draw.rect(self.screen, fill, rect, border_radius=14)
            pygame.draw.rect(self.screen, self.theme.panel_background, rect, width=2, border_radius=14)

            label_color = self.theme.heading_text if action.enabled else (215, 215, 215)
            desc_color = self.theme.muted_text if action.enabled else (225, 225, 225)
            label = self.button_font.render(action.label, True, label_color)
            desc = self.small_font.render(action.description, True, desc_color)
            self.screen.blit(label, (rect.x + 18, rect.y + 9))
            self.screen.blit(desc, (rect.x + 18, rect.y + 36))

        notes = [
            "Promotion picker, captures, move history, and theme rotation are live.",
            "Engine play is still held back until the NN evaluator is trained.",
            "Stockfish now feeds the training and move-review pipeline in code.",
        ]
        for index, line in enumerate(notes):
            text = self.small_font.render(line, True, self.theme.win_banner_text)
            self.screen.blit(text, (card_rect.x + 430, card_rect.y + 248 + index * 30))

        hint = self.small_font.render("Enter starts local play. Esc quits.", True, self.theme.win_banner_text)
        self.screen.blit(hint, (card_rect.x + 46, card_rect.bottom - 42))

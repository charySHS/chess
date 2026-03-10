from __future__ import annotations

import pygame

from src.ui.game_scene import GameScene
from src.ui.menu_scene import MenuScene
from src.ui.theme import Theme, build_theme, next_theme_name


class App:
    def __init__(self, screen: pygame.Surface, theme: Theme) -> None:
        self.screen = screen
        self.theme = theme
        self.running = True
        self.menu_scene = MenuScene(
            screen=screen,
            theme=theme,
            start_local_game=self.start_local_game,
            cycle_theme=self.cycle_theme,
            request_quit=self.stop,
        )
        self.game_scene = GameScene(
            screen=screen,
            theme=theme,
            return_to_menu=self.show_menu,
            request_quit=self.stop,
            cycle_theme=self.cycle_theme,
        )
        self.active_scene = "menu"

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            for event in pygame.event.get():
                self.current_scene().handle_event(event)

            self.current_scene().draw()
            clock.tick(self.theme.fps)

    def current_scene(self) -> MenuScene | GameScene:
        if self.active_scene == "game":
            return self.game_scene
        return self.menu_scene

    def start_local_game(self) -> None:
        self.game_scene.reset_board()
        self.active_scene = "game"

    def show_menu(self) -> None:
        self.active_scene = "menu"

    def cycle_theme(self) -> None:
        self.theme = build_theme(next_theme_name(self.theme.name))
        self.menu_scene.set_theme(self.theme)
        self.game_scene.set_theme(self.theme)

    def stop(self) -> None:
        self.running = False

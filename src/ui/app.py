from __future__ import annotations

import pygame

from src.ui.game_scene import GameScene
from src.ui.menu_scene import MenuScene
from src.ui.theme import Theme, build_theme, next_theme_name, resize_theme


class App:
    def __init__(self, screen: pygame.Surface, theme: Theme) -> None:
        self.screen = screen
        self.theme = theme
        self.running = True
        self.fullscreen = False
        self.menu_scene = MenuScene(
            screen=screen,
            theme=theme,
            start_local_game=self.start_local_game,
            start_engine_game=self.start_engine_game,
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
        self.menu_scene.activate()

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            for event in pygame.event.get():
                if self._handle_global_event(event):
                    continue
                self.current_scene().handle_event(event)

            self.current_scene().update()
            self.current_scene().draw()
            clock.tick(self.theme.fps)

    def _handle_global_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            self.toggle_fullscreen()
            return True
        if event.type == pygame.VIDEORESIZE and not self.fullscreen:
            self.resize_window(event.w, event.h)
            return True
        return False

    def current_scene(self) -> MenuScene | GameScene:
        if self.active_scene == "game":
            return self.game_scene
        return self.menu_scene

    def start_local_game(self) -> None:
        self.game_scene.configure_mode("local")
        self.game_scene.reset_board()
        self.active_scene = "game"

    def start_engine_game(self) -> None:
        self.game_scene.configure_mode("engine")
        self.game_scene.reset_board()
        self.active_scene = "game"

    def show_menu(self) -> None:
        self.active_scene = "menu"
        self.menu_scene.activate()

    def cycle_theme(self) -> None:
        resized = resize_theme(build_theme(next_theme_name(self.theme.name)), self.theme.window_width, self.theme.window_height)
        self._apply_theme(resized)

    def stop(self) -> None:
        self.running = False

    def resize_window(self, width: int, height: int) -> None:
        self.theme = resize_theme(self.theme, width, height)
        self.screen = pygame.display.set_mode((self.theme.window_width, self.theme.window_height), pygame.RESIZABLE)
        self._update_scene_surfaces()
        self._apply_theme(self.theme)

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            display = pygame.display.get_desktop_sizes()[0]
            self.theme = resize_theme(self.theme, display[0], display[1])
            self.screen = pygame.display.set_mode(display, pygame.FULLSCREEN)
        else:
            self.theme = resize_theme(self.theme, self.theme.min_window_width, self.theme.min_window_height)
            self.screen = pygame.display.set_mode((self.theme.window_width, self.theme.window_height), pygame.RESIZABLE)
        self._update_scene_surfaces()
        self._apply_theme(self.theme)

    def _apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.menu_scene.set_theme(self.theme)
        self.game_scene.set_theme(self.theme)

    def _update_scene_surfaces(self) -> None:
        self.menu_scene.set_screen(self.screen)
        self.game_scene.set_screen(self.screen)

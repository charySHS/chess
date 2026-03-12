from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.config import AppConfig
from src.ui.theme import build_theme


def _run_pygame(theme_name: str) -> None:
    import pygame

    from src.ui.app import App

    pygame.init()
    try:
        theme = build_theme(theme_name)
        screen = pygame.display.set_mode((theme.window_width, theme.window_height), pygame.RESIZABLE)
        pygame.display.set_caption("NewChess")
        App(screen, theme).run()
    finally:
        pygame.quit()


def _run_kivy(theme_name: str) -> None:
    theme = build_theme(theme_name)
    from src.ui_kivy.app import run_kivy_app

    run_kivy_app(theme)


def main() -> None:
    config = AppConfig()
    backend = config.ui_backend.strip().lower()
    if backend == "kivy":
        try:
            _run_kivy(config.theme_name)
            return
        except ModuleNotFoundError as exc:
            if exc.name and exc.name.startswith("kivy"):
                raise RuntimeError(
                    "Kivy backend requested but Kivy is not installed. "
                    "Install dependencies from requirements.txt or set NEWCHESS_UI_BACKEND=pygame to force the legacy frontend."
                ) from exc
            raise
    _run_pygame(config.theme_name)


if __name__ == "__main__":
    main()

from __future__ import annotations

import sys
from pathlib import Path

import pygame

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.ui.app import App
from src.ui.theme import build_theme


def main() -> None:
    pygame.init()
    try:
        theme = build_theme("classic")
        screen = pygame.display.set_mode((theme.window_width, theme.window_height))
        pygame.display.set_caption("NewChess")
        App(screen, theme).run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class Theme:
    name: str = "classic"
    window_width: int = 980
    window_height: int = 772
    board_size: int = 640
    square_size: int = 80
    board_margin: int = 24
    status_height: int = 84
    fps: int = 60

    light_square: tuple[int, int, int] = (241, 217, 181)
    dark_square: tuple[int, int, int] = (181, 136, 99)
    background: tuple[int, int, int] = (28, 32, 38)
    panel_background: tuple[int, int, int] = (20, 23, 28)
    side_panel_background: tuple[int, int, int] = (33, 39, 47)
    side_panel_accent: tuple[int, int, int] = (191, 146, 88)
    coord_text: tuple[int, int, int] = (224, 224, 224)
    status_text: tuple[int, int, int] = (238, 238, 238)
    heading_text: tuple[int, int, int] = (248, 240, 229)
    muted_text: tuple[int, int, int] = (182, 186, 193)
    last_move_fill: tuple[int, int, int, int] = (246, 246, 105, 108)
    selected_outline: tuple[int, int, int] = (78, 172, 255)
    legal_quiet_fill: tuple[int, int, int, int] = (58, 148, 74, 150)
    legal_capture_outline: tuple[int, int, int, int] = (206, 68, 62, 220)
    drag_shadow: tuple[int, int, int, int] = (0, 0, 0, 70)
    overlay_fill: tuple[int, int, int, int] = (8, 11, 15, 170)
    win_banner: tuple[int, int, int] = (228, 214, 188)
    win_banner_text: tuple[int, int, int] = (26, 29, 33)
    promotion_panel: tuple[int, int, int] = (238, 231, 217)
    promotion_text: tuple[int, int, int] = (28, 31, 35)

    piece_size_normal: int = 80
    piece_size_dragged: int = 120
    quiet_move_radius: int = 12
    capture_ring_width: int = 5
    selected_outline_width: int = 4
    label_font_size: int = 18
    status_font_size: int = 24
    panel_title_font_size: int = 28
    panel_body_font_size: int = 20
    panel_small_font_size: int = 16

    @property
    def board_origin(self) -> tuple[int, int]:
        return (self.board_margin, self.board_margin)

    @property
    def board_rect(self) -> tuple[int, int, int, int]:
        x, y = self.board_origin
        return (x, y, self.board_size, self.board_size)

    @property
    def side_panel_rect(self) -> tuple[int, int, int, int]:
        x = self.board_margin * 2 + self.board_size
        y = self.board_margin
        width = self.window_width - x - self.board_margin
        height = self.board_size
        return (x, y, width, height)


THEME_PRESETS: dict[str, dict[str, tuple[int, int, int] | tuple[int, int, int, int] | str]] = {
    "classic": {},
    "midnight": {
        "light_square": (149, 162, 189),
        "dark_square": (71, 87, 118),
        "background": (12, 18, 28),
        "panel_background": (10, 14, 22),
        "side_panel_background": (21, 28, 42),
        "side_panel_accent": (120, 182, 255),
        "coord_text": (232, 240, 250),
        "status_text": (242, 245, 250),
        "heading_text": (236, 244, 255),
        "muted_text": (171, 187, 208),
        "selected_outline": (255, 210, 96),
        "legal_quiet_fill": (76, 205, 132, 150),
        "legal_capture_outline": (255, 124, 104, 220),
        "win_banner": (219, 229, 245),
        "promotion_panel": (224, 234, 249),
    },
    "ivory": {
        "light_square": (242, 236, 221),
        "dark_square": (154, 133, 112),
        "background": (239, 233, 223),
        "panel_background": (59, 54, 48),
        "side_panel_background": (73, 66, 58),
        "side_panel_accent": (214, 176, 110),
        "coord_text": (66, 58, 50),
        "status_text": (242, 234, 223),
        "heading_text": (247, 238, 227),
        "muted_text": (221, 207, 188),
        "last_move_fill": (255, 227, 117, 120),
        "selected_outline": (78, 134, 173),
        "legal_quiet_fill": (52, 127, 84, 146),
        "legal_capture_outline": (184, 73, 58, 220),
        "win_banner": (245, 236, 220),
        "win_banner_text": (50, 43, 35),
        "promotion_panel": (248, 239, 225),
        "promotion_text": (42, 39, 34),
    },
}

THEME_ORDER = ["classic", "midnight", "ivory"]

PIECE_CODE_TO_NAME = {
    "P": "wp",
    "N": "wn",
    "B": "wb",
    "R": "wr",
    "Q": "wq",
    "K": "wk",
    "p": "bp",
    "n": "bn",
    "b": "bb",
    "r": "br",
    "q": "bq",
    "k": "bk",
}

LEGACY_FILENAME_MAP = {
    "wp": "white_pawn.png",
    "wn": "white_knight.png",
    "wb": "white_bishop.png",
    "wr": "white_rook.png",
    "wq": "white_queen.png",
    "wk": "white_king.png",
    "bp": "black_pawn.png",
    "bn": "black_knight.png",
    "bb": "black_bishop.png",
    "br": "black_rook.png",
    "bq": "black_queen.png",
    "bk": "black_king.png",
}


def build_theme(name: str) -> Theme:
    base = Theme()
    preset = THEME_PRESETS.get(name, THEME_PRESETS["classic"])
    return replace(base, name=name, **preset)


def next_theme_name(current: str) -> str:
    try:
        index = THEME_ORDER.index(current)
    except ValueError:
        return THEME_ORDER[0]
    return THEME_ORDER[(index + 1) % len(THEME_ORDER)]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sprite_directory_candidates(size: int) -> list[Path]:
    root = repo_root()
    candidates: list[Path] = []

    if size == 80:
        candidates.extend(
            [
                root / "assets" / "pieces_80",
                root / "src" / "assets" / "pieces_80",
                root / "src" / "assets" / "images" / "imgs-80px",
            ]
        )
    else:
        candidates.extend(
            [
                root / "assets" / "pieces_120",
                root / "src" / "assets" / "pieces_120",
                root / "src" / "assets" / "images" / "imgs-120px",
                root / "src" / "assets" / "images" / "imgs-128px",
            ]
        )

    return candidates

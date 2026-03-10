from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class Theme:
    name: str = "glass"
    window_width: int = 980
    window_height: int = 772
    board_size: int = 640
    square_size: int = 80
    board_margin: int = 24
    status_height: int = 84
    fps: int = 60

    light_square: tuple[int, int, int] = (233, 241, 249)
    dark_square: tuple[int, int, int] = (152, 182, 205)
    background: tuple[int, int, int] = (10, 16, 28)
    background_alt: tuple[int, int, int] = (31, 58, 97)
    panel_background: tuple[int, int, int] = (16, 22, 35)
    side_panel_background: tuple[int, int, int] = (24, 32, 48)
    side_panel_accent: tuple[int, int, int] = (150, 229, 255)
    coord_text: tuple[int, int, int] = (225, 239, 255)
    status_text: tuple[int, int, int] = (246, 250, 255)
    heading_text: tuple[int, int, int] = (245, 249, 255)
    muted_text: tuple[int, int, int] = (191, 213, 233)
    last_move_fill: tuple[int, int, int, int] = (255, 246, 157, 112)
    selected_outline: tuple[int, int, int] = (118, 224, 255)
    legal_quiet_fill: tuple[int, int, int, int] = (92, 233, 174, 150)
    legal_capture_outline: tuple[int, int, int, int] = (255, 127, 118, 220)
    drag_shadow: tuple[int, int, int, int] = (0, 0, 0, 76)
    overlay_fill: tuple[int, int, int, int] = (7, 12, 20, 156)
    win_banner: tuple[int, int, int] = (214, 238, 255)
    win_banner_text: tuple[int, int, int] = (20, 30, 40)
    promotion_panel: tuple[int, int, int] = (224, 242, 255)
    promotion_text: tuple[int, int, int] = (26, 35, 45)

    glass_fill: tuple[int, int, int, int] = (255, 255, 255, 42)
    glass_fill_strong: tuple[int, int, int, int] = (255, 255, 255, 64)
    glass_border: tuple[int, int, int, int] = (255, 255, 255, 108)
    glass_highlight: tuple[int, int, int, int] = (255, 255, 255, 78)
    glass_shadow: tuple[int, int, int, int] = (8, 14, 24, 72)
    board_frame: tuple[int, int, int, int] = (255, 255, 255, 38)
    orb_primary: tuple[int, int, int, int] = (92, 201, 255, 74)
    orb_secondary: tuple[int, int, int, int] = (118, 242, 210, 64)
    orb_tertiary: tuple[int, int, int, int] = (255, 164, 124, 56)

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
    "glass": {},
    "midnight": {
        "light_square": (193, 212, 240),
        "dark_square": (94, 122, 173),
        "background": (4, 8, 19),
        "background_alt": (24, 36, 76),
        "side_panel_accent": (132, 171, 255),
        "selected_outline": (245, 220, 130),
        "orb_primary": (86, 146, 255, 70),
        "orb_secondary": (137, 100, 255, 64),
        "orb_tertiary": (88, 220, 214, 58),
        "win_banner": (220, 228, 255),
        "promotion_panel": (215, 226, 255),
    },
    "ivory": {
        "light_square": (248, 243, 234),
        "dark_square": (197, 178, 157),
        "background": (234, 226, 214),
        "background_alt": (197, 175, 151),
        "coord_text": (63, 56, 49),
        "status_text": (245, 241, 234),
        "heading_text": (252, 248, 243),
        "muted_text": (228, 219, 206),
        "selected_outline": (87, 164, 190),
        "legal_quiet_fill": (72, 149, 118, 144),
        "panel_background": (69, 61, 52),
        "side_panel_background": (88, 78, 68),
        "side_panel_accent": (230, 193, 132),
        "glass_fill": (255, 255, 255, 58),
        "glass_fill_strong": (255, 255, 255, 88),
        "glass_border": (255, 255, 255, 132),
        "glass_shadow": (71, 54, 36, 64),
        "orb_primary": (255, 202, 143, 66),
        "orb_secondary": (142, 199, 212, 58),
        "orb_tertiary": (190, 150, 110, 58),
        "win_banner": (252, 245, 234),
        "win_banner_text": (52, 46, 40),
        "promotion_panel": (255, 247, 237),
        "promotion_text": (58, 49, 40),
    },
}

THEME_ORDER = ["glass", "midnight", "ivory"]

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
    preset = THEME_PRESETS.get(name, THEME_PRESETS["glass"])
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

from __future__ import annotations

from math import sin

import pygame

from src.ui.theme import Theme


def draw_gradient_backdrop(surface: pygame.Surface, theme: Theme, *, grid_spacing: int) -> None:
    for y in range(theme.window_height):
        ratio = y / max(1, theme.window_height - 1)
        color = tuple(
            int(theme.background[index] * (1.0 - ratio) + theme.background_alt[index] * ratio)
            for index in range(3)
        )
        pygame.draw.line(surface, color, (0, y), (theme.window_width, y))

    grid = pygame.Surface((theme.window_width, theme.window_height), pygame.SRCALPHA)
    for x in range(0, theme.window_width, grid_spacing):
        pygame.draw.line(grid, theme.background_grid, (x, 0), (x, theme.window_height))
    for y in range(0, theme.window_height, grid_spacing):
        pygame.draw.line(grid, theme.background_grid, (0, y), (theme.window_width, y))
    surface.blit(grid, (0, 0))

    glow_radius = max(theme.window_width, theme.window_height) // 3
    glow = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
    for ring in range(glow_radius, 0, -18):
        alpha = max(0, min(255, int(32 * (ring / glow_radius))))
        pygame.draw.circle(glow, (*theme.background_glow, alpha), (glow_radius, glow_radius), ring)
    surface.blit(glow, (-glow_radius // 3, -glow_radius // 4))
    surface.blit(glow, (theme.window_width - glow_radius, theme.window_height - int(glow_radius * 1.15)))


def draw_orb(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int, int],
    phase: float,
) -> None:
    orb = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    alpha = max(0, min(255, int(color[3] + 10 * sin(phase))))
    pygame.draw.circle(orb, (color[0], color[1], color[2], alpha), (radius, radius), radius)
    surface.blit(orb, (center[0] - radius, center[1] - radius + int(6 * sin(phase))))


def draw_glass_panel(
    surface: pygame.Surface,
    theme: Theme,
    rect: pygame.Rect,
    *,
    radius: int,
    strong: bool = False,
) -> None:
    shadow = pygame.Surface((rect.width + 26, rect.height + 28), pygame.SRCALPHA)
    pygame.draw.rect(shadow, theme.glass_shadow, shadow.get_rect(), border_radius=radius + 8)
    surface.blit(shadow, (rect.x - 8, rect.y + 14))

    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    fill = theme.glass_fill_strong if strong else theme.glass_fill
    pygame.draw.rect(panel, fill, panel.get_rect(), border_radius=radius)
    pygame.draw.rect(panel, theme.glass_border, panel.get_rect(), width=1, border_radius=radius)
    inner = panel.get_rect().inflate(-10, -10)
    pygame.draw.rect(panel, theme.glass_fill_soft, inner, width=1, border_radius=max(8, radius - 6))
    shine = pygame.Rect(8, 8, rect.width - 16, max(18, rect.height // 6))
    pygame.draw.rect(panel, theme.glass_highlight, shine, border_radius=radius)
    edge_glow = pygame.Rect(10, rect.height - max(18, rect.height // 6), rect.width - 20, max(8, rect.height // 8))
    pygame.draw.rect(panel, theme.glass_edge_glow, edge_glow, border_radius=radius)
    surface.blit(panel, rect.topleft)


def draw_glass_pill(surface: pygame.Surface, theme: Theme, rect: pygame.Rect, *, radius: int = 18) -> None:
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, theme.glass_fill_soft, panel.get_rect(), border_radius=radius)
    pygame.draw.rect(panel, theme.glass_border, panel.get_rect(), width=1, border_radius=radius)
    surface.blit(panel, rect.topleft)


def draw_glass_button(
    surface: pygame.Surface,
    theme: Theme,
    rect: pygame.Rect,
    *,
    hovered: bool,
    enabled: bool,
    phase: float,
    radius: int = 20,
) -> None:
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    fill = theme.glass_fill_strong if enabled else (255, 255, 255, 28)
    if hovered:
        fill = (fill[0], fill[1], fill[2], min(fill[3] + 24, 160))
    pygame.draw.rect(panel, fill, panel.get_rect(), border_radius=radius)
    pygame.draw.rect(panel, theme.glass_border, panel.get_rect(), width=1, border_radius=radius)
    inner = panel.get_rect().inflate(-10, -10)
    pygame.draw.rect(panel, theme.glass_fill_soft, inner, width=1, border_radius=max(8, radius - 4))
    highlight = pygame.Rect(6, 6, rect.width - 12, 16)
    pulse_alpha = max(0, min(255, int(theme.glass_highlight[3] + 14 * sin(phase * 2.2))))
    pygame.draw.rect(panel, (255, 255, 255, pulse_alpha), highlight, border_radius=16)
    accent = pygame.Rect(16, rect.height - 7, rect.width - 32, 3)
    pygame.draw.rect(panel, theme.side_panel_accent_soft, accent, border_radius=4)
    surface.blit(panel, rect.topleft)


def draw_glass_chip(
    surface: pygame.Surface,
    theme: Theme,
    rect: pygame.Rect,
    *,
    label: str,
    font: pygame.font.Font,
    text_color: tuple[int, int, int],
) -> None:
    chip = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(chip, theme.glass_fill_soft, chip.get_rect(), border_radius=14)
    pygame.draw.rect(chip, theme.glass_border, chip.get_rect(), width=1, border_radius=14)
    inner = chip.get_rect().inflate(-8, -8)
    pygame.draw.rect(chip, theme.glass_fill_soft, inner, width=1, border_radius=10)
    surface.blit(chip, rect.topleft)
    blit_fit_text(surface, font, label, text_color, rect.inflate(-8, -6), center=True)


def blit_fit_text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    rect: pygame.Rect,
    *,
    center: bool = False,
) -> None:
    fitted = text
    while fitted and font.size(fitted)[0] > rect.width:
        fitted = fitted[:-1]
    if fitted != text and len(fitted) > 3:
        fitted = fitted[:-3].rstrip() + "..."
    text_surface = font.render(fitted, True, color)
    previous_clip = surface.get_clip()
    surface.set_clip(rect)
    destination = text_surface.get_rect(center=rect.center) if center else text_surface.get_rect(topleft=rect.topleft)
    surface.blit(text_surface, destination)
    surface.set_clip(previous_clip)

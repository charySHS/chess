from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from src.chess_core import Board, generate_legal_moves
from src.ui.game_scene import GameScene


def _apply_uci(board: Board, uci: str) -> None:
    move = next(move for move in generate_legal_moves(board) if move.uci() == uci)
    board.make_move(move)


def test_threefold_repetition_is_detected() -> None:
    board = Board()

    cycle = ("g1f3", "g8f6", "f3g1", "f6g8")
    for _ in range(2):
        for uci in cycle:
            _apply_uci(board, uci)

    assert board.is_threefold_repetition()
    assert board.repetition_count() == 3


def test_local_mode_auto_flips_to_side_to_move() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        scene = GameScene(pygame.Surface((1280, 900)))
        scene.configure_mode("local")

        assert scene.flipped is False

        white_move = next(move for move in scene.legal_moves if move.uci() == "e2e4")
        scene.apply_move(white_move)
        assert scene.flipped is True

        black_move = next(move for move in scene.legal_moves if move.uci() == "e7e5")
        scene.apply_move(black_move)
        assert scene.flipped is False
    finally:
        scene.close()
        pygame.quit()


def test_game_scene_declares_draw_by_repetition() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        scene = GameScene(pygame.Surface((1280, 900)))
        scene.configure_mode("local")

        for uci in ("g1f3", "g8f6", "f3g1", "f6g8") * 2:
            move = next(move for move in scene.legal_moves if move.uci() == uci)
            scene.apply_move(move)

        assert scene.result.is_over is True
        assert scene.result.reason == "repetition"
    finally:
        scene.close()
        pygame.quit()


def test_rook_capture_triggers_alert_banner() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        scene = GameScene(pygame.Surface((1280, 900)))
        scene.board = Board("6k1/8/8/8/8/8/r3Q3/4K3 w - - 0 1")
        scene.refresh_legal_moves()

        move = next(move for move in scene.legal_moves if move.uci() == "e2a2")
        scene.apply_move(move)

        assert scene.rook_alert_text() == "Rook down."
    finally:
        scene.close()
        pygame.quit()

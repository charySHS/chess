from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pygame

from src.chess_core.constants import EMPTY
from src.chess_core.move import Move


SquareLookup = Callable[[tuple[int, int]], int | None]
PieceLookup = Callable[[int], str]
MovesLookup = Callable[[int], list[Move]]
MoveApplier = Callable[[Move], None]
ActionCallback = Callable[[], None]


@dataclass(frozen=True)
class MoveResolution:
    move: Move | None = None
    awaiting_choice: bool = False


MoveResolver = Callable[[list[Move]], MoveResolution]


@dataclass
class InputState:
    selected_square: int | None = None
    hover_square: int | None = None
    legal_moves: list[Move] = field(default_factory=list)
    drag_origin: int | None = None
    drag_position: tuple[int, int] | None = None
    mouse_down_position: tuple[int, int] | None = None
    is_dragging: bool = False
    mouse_down: bool = False

    def clear(self) -> None:
        self.selected_square = None
        self.hover_square = None
        self.legal_moves = []
        self.drag_origin = None
        self.drag_position = None
        self.mouse_down_position = None
        self.is_dragging = False
        self.mouse_down = False


class InputHandler:
    def __init__(
        self,
        square_at_pixel: SquareLookup,
        piece_at_square: PieceLookup,
        legal_moves_for_square: MovesLookup,
        resolve_move_choice: MoveResolver,
        apply_move: MoveApplier,
        reset_board: ActionCallback,
        undo_move: ActionCallback,
        toggle_flip: ActionCallback,
        cycle_theme: ActionCallback,
        return_to_menu: ActionCallback,
        request_quit: ActionCallback,
        interaction_allowed: Callable[[], bool],
    ) -> None:
        self.square_at_pixel = square_at_pixel
        self.piece_at_square = piece_at_square
        self.legal_moves_for_square = legal_moves_for_square
        self.resolve_move_choice = resolve_move_choice
        self.apply_move = apply_move
        self.reset_board = reset_board
        self.undo_move = undo_move
        self.toggle_flip = toggle_flip
        self.cycle_theme = cycle_theme
        self.return_to_menu = return_to_menu
        self.request_quit = request_quit
        self.interaction_allowed = interaction_allowed
        self.state = InputState()

    def reset_interaction(self) -> None:
        self.state.clear()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.request_quit()
            return

        if event.type == pygame.KEYDOWN:
            self._handle_keydown(event)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse_down(event.pos)
            return

        if event.type == pygame.MOUSEMOTION:
            self._handle_mouse_motion(event.pos)
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._handle_mouse_up(event.pos)

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_ESCAPE:
            self.request_quit()
        elif event.key == pygame.K_r:
            self.reset_board()
            self.reset_interaction()
        elif event.key == pygame.K_u:
            self.undo_move()
            self.reset_interaction()
        elif event.key == pygame.K_f:
            self.toggle_flip()
        elif event.key == pygame.K_t:
            self.cycle_theme()
        elif event.key == pygame.K_m:
            self.return_to_menu()

    def _handle_mouse_down(self, mouse_pos: tuple[int, int]) -> None:
        if not self.interaction_allowed():
            return

        square = self.square_at_pixel(mouse_pos)
        self.state.hover_square = square
        if square is None:
            self.reset_interaction()
            return

        if self.state.selected_square is not None:
            matching_moves = [move for move in self.state.legal_moves if move.to_square == square]
            if matching_moves and square != self.state.selected_square:
                resolution = self.resolve_move_choice(matching_moves)
                if resolution.move is not None:
                    self.apply_move(resolution.move)
                    self.reset_interaction()
                return

        piece = self.piece_at_square(square)
        legal_moves = self.legal_moves_for_square(square)
        if piece == EMPTY or not legal_moves:
            self.reset_interaction()
            return

        self.state.selected_square = square
        self.state.legal_moves = legal_moves
        self.state.drag_origin = square
        self.state.drag_position = mouse_pos
        self.state.mouse_down_position = mouse_pos
        self.state.is_dragging = False
        self.state.mouse_down = True

    def _handle_mouse_motion(self, mouse_pos: tuple[int, int]) -> None:
        self.state.hover_square = self.square_at_pixel(mouse_pos)
        if self.state.drag_origin is None or not self.state.mouse_down:
            return

        if self.state.mouse_down_position is not None:
            dx = mouse_pos[0] - self.state.mouse_down_position[0]
            dy = mouse_pos[1] - self.state.mouse_down_position[1]
            if dx * dx + dy * dy < 36:
                return

        self.state.is_dragging = True
        self.state.drag_position = mouse_pos

    def _handle_mouse_up(self, mouse_pos: tuple[int, int]) -> None:
        if not self.interaction_allowed():
            self.reset_interaction()
            return

        if self.state.selected_square is None:
            return

        was_dragging = self.state.is_dragging
        target_square = self.square_at_pixel(mouse_pos)
        self.state.hover_square = target_square
        resolution = MoveResolution()
        if was_dragging and target_square is not None:
            matching_moves = [move for move in self.state.legal_moves if move.to_square == target_square]
            if matching_moves:
                resolution = self.resolve_move_choice(matching_moves)

        self.state.is_dragging = False
        self.state.drag_position = None
        self.state.drag_origin = None
        self.state.mouse_down_position = None
        self.state.mouse_down = False

        if resolution.move is not None:
            self.apply_move(resolution.move)
            self.reset_interaction()

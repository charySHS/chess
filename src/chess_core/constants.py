# chess_core/constants.py

from __future__ import annotations

WHITE = "w"
BLACK = "b"

FILES = "abcdefgh"
RANKS = "12345678"

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

EMPTY = "."

WHITE_PIECES = {"P", "N", "B", "R", "Q", "K"}
BLACK_PIECES = {"p", "n", "b", "r", "q", "k"}

PIECE_TYPES = {"P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k"}

PIECE_VALUES = {
    "P": 100,
    "N": 300,
    "B": 300,
    "R": 500,
    "Q": 900,
    "K": 0,
    "p": -100,
    "n": -300,
    "b": -300,
    "r": -500,
    "q": -500,
    "k": 0
}
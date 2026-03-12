from __future__ import annotations

from dataclasses import dataclass


EXACT = "exact"
LOWERBOUND = "lowerbound"
UPPERBOUND = "upperbound"


@dataclass(frozen=True)
class TTEntry:
    depth: int
    score: float
    flag: str
    best_move_uci: str | None


class TranspositionTable:
    def __init__(self) -> None:
        self._entries: dict[int, TTEntry] = {}

    def get(self, key: int) -> TTEntry | None:
        return self._entries.get(key)

    def store(self, key: int, entry: TTEntry) -> None:
        existing = self._entries.get(key)
        if existing is None or entry.depth >= existing.depth:
            self._entries[key] = entry

    def clear(self) -> None:
        self._entries.clear()

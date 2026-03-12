from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from src.chess_core import Board, Move
from src.config import AppConfig


@dataclass(frozen=True)
class Score:
    cp: int | None = None
    mate: int | None = None

    def as_centipawns(self) -> int:
        if self.cp is not None:
            return self.cp
        if self.mate is None:
            return 0
        sign = 1 if self.mate > 0 else -1
        return sign * (100000 - min(abs(self.mate), 1000) * 100)


@dataclass(frozen=True)
class EngineLine:
    multipv: int
    score: Score
    pv: list[str]


@dataclass(frozen=True)
class PositionAnalysis:
    fen: str
    depth: int
    lines: list[EngineLine]

    @property
    def best_line(self) -> EngineLine | None:
        return self.lines[0] if self.lines else None


@dataclass(frozen=True)
class MoveReview:
    played_move: str
    best_move: str | None
    played_score: Score
    best_score: Score
    loss_cp: int
    label: str


class StockfishBridge:
    def __init__(self, path: str | Path | None = None, default_depth: int | None = None) -> None:
        config = AppConfig()
        self.path = str(path or config.stockfish_path)
        self.default_depth = default_depth or config.stockfish_depth
        self.process: subprocess.Popen[str] | None = None
        self.stdout: TextIO | None = None
        self.stdin: TextIO | None = None

    def __enter__(self) -> StockfishBridge:
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def open(self) -> None:
        if self.process is not None:
            return
        self.process = subprocess.Popen(
            [self.path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("Failed to open Stockfish pipes.")
        self.stdin = self.process.stdin
        self.stdout = self.process.stdout
        self._send("uci")
        self._read_until("uciok")
        self._send("isready")
        self._read_until("readyok")

    def close(self) -> None:
        if self.process is None:
            return
        try:
            self._send("quit")
        except Exception:
            pass
        self.process.kill()
        self.process = None
        self.stdin = None
        self.stdout = None

    def analyse_fen(self, fen: str, depth: int | None = None, multipv: int = 1) -> PositionAnalysis:
        self.open()
        assert self.stdout is not None
        target_depth = depth or self.default_depth
        self._send(f"setoption name MultiPV value {multipv}")
        self._send(f"position fen {fen}")
        self._send(f"go depth {target_depth}")

        lines_by_pv: dict[int, EngineLine] = {}
        while True:
            line = self.stdout.readline().strip()
            if not line:
                continue
            if line.startswith("info") and " pv " in line and " score " in line:
                parsed = self._parse_info_line(line)
                if parsed is not None:
                    lines_by_pv[parsed.multipv] = parsed
            if line.startswith("bestmove"):
                break

        ordered = [lines_by_pv[index] for index in sorted(lines_by_pv)]
        return PositionAnalysis(fen=fen, depth=target_depth, lines=ordered)

    def best_move_for_fen(self, fen: str, depth: int | None = None) -> str | None:
        analysis = self.analyse_fen(fen, depth=depth, multipv=1)
        if analysis.best_line is None or not analysis.best_line.pv:
            return None
        return analysis.best_line.pv[0]

    def review_move(self, board_before: Board, move: Move, depth: int | None = None) -> MoveReview:
        before_fen = board_before.to_fen()
        best_analysis = self.analyse_fen(before_fen, depth=depth, multipv=2)
        best_line = best_analysis.best_line
        runner_up = best_analysis.lines[1] if len(best_analysis.lines) > 1 else None

        played_board = Board(before_fen)
        played_board.make_move(move)
        played_analysis = self.analyse_fen(played_board.to_fen(), depth=depth, multipv=1)

        best_score = best_line.score if best_line is not None else Score(cp=0)
        played_reply_score = played_analysis.best_line.score if played_analysis.best_line is not None else Score(cp=0)
        played_score = Score(cp=-played_reply_score.as_centipawns())
        loss_cp = max(0, best_score.as_centipawns() - played_score.as_centipawns())
        best_move = best_line.pv[0] if best_line is not None and best_line.pv else None
        best_margin_cp = None
        if runner_up is not None:
            best_margin_cp = max(0, best_score.as_centipawns() - runner_up.score.as_centipawns())
        label = classify_move_loss(loss_cp, move.uci(), best_move, best_margin_cp=best_margin_cp)
        return MoveReview(
            played_move=move.uci(),
            best_move=best_move,
            played_score=played_score,
            best_score=best_score,
            loss_cp=loss_cp,
            label=label,
        )

    def _send(self, command: str) -> None:
        if self.stdin is None:
            raise RuntimeError("Stockfish process is not open.")
        self.stdin.write(command + "\n")
        self.stdin.flush()

    def _read_until(self, token: str) -> None:
        assert self.stdout is not None
        while True:
            line = self.stdout.readline()
            if not line:
                raise RuntimeError(f"Stockfish terminated before sending '{token}'.")
            if token in line:
                return

    def _parse_info_line(self, line: str) -> EngineLine | None:
        parts = line.split()
        try:
            multipv = int(parts[parts.index("multipv") + 1]) if "multipv" in parts else 1
            score_index = parts.index("score")
            score_type = parts[score_index + 1]
            score_value = int(parts[score_index + 2])
            pv_index = parts.index("pv")
        except (ValueError, IndexError):
            return None

        score = Score(cp=score_value) if score_type == "cp" else Score(mate=score_value)
        pv = parts[pv_index + 1 :]
        return EngineLine(multipv=multipv, score=score, pv=pv)


def classify_move_loss(
    loss_cp: int,
    played_move: str,
    best_move: str | None,
    *,
    best_margin_cp: int | None = None,
) -> str:
    exact_best = best_move is not None and played_move == best_move
    if exact_best and (best_margin_cp is None or best_margin_cp >= 35):
        return "best"
    if loss_cp <= 12:
        return "great"
    if loss_cp <= 38:
        return "good"
    if loss_cp <= 95:
        return "inaccuracy"
    if loss_cp <= 180:
        return "mistake"
    return "blunder"

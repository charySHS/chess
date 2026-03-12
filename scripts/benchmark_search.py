from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.chess_core import Board, START_FEN
from src.engine.search import SearchEngine


BENCH_POSITIONS = (
    ("start", START_FEN),
    ("middlegame", "r2q1rk1/ppp2ppp/2npbn2/3Np3/2B1P3/2N5/PPP2PPP/R1BQ1RK1 w - - 0 1"),
    ("tactical", "r1bq1rk1/ppp2ppp/2np1n2/4p3/2BPP3/2N2N2/PPP2PPP/R1BQ1RK1 w - - 2 8"),
    ("endgame", "8/2p5/2P1k3/3p4/3P4/4K3/8/8 w - - 0 1"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark NewChess search.")
    parser.add_argument("--depth", type=int, default=4, help="Search depth per position.")
    args = parser.parse_args()

    engine = SearchEngine()
    total_nodes = 0
    total_time = 0.0

    for label, fen in BENCH_POSITIONS:
        board = Board(fen)
        started = perf_counter()
        result = engine.iterative_deepening(board, max_depth=args.depth)
        elapsed = perf_counter() - started
        total_nodes += result.nodes
        total_time += elapsed
        nps = int(result.nodes / elapsed) if elapsed > 0 else 0
        best = result.best_move.uci() if result.best_move is not None else "--"
        print(
            f"{label:10s} depth={args.depth} best={best:6s} "
            f"score={result.score:8.1f} nodes={result.nodes:8d} time={elapsed:6.3f}s nps={nps:8d}"
        )

    overall_nps = int(total_nodes / total_time) if total_time > 0 else 0
    print(
        f"total      depth={args.depth} nodes={total_nodes:8d} time={total_time:6.3f}s nps={overall_nps:8d}"
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.config import AppConfig
from src.engine.lab import LabConfig, run_lab_cycle
from src.engine.profile import default_snapshot_path, load_engine_profile


def main() -> None:
    app_config = AppConfig()

    parser = argparse.ArgumentParser(description="Run the NewChess self-improvement lab cycle.")
    parser.add_argument("--snapshot", type=Path, default=default_snapshot_path())
    parser.add_argument("--snapshot-name", type=str, default="baseline_v1")
    parser.add_argument("--take-snapshot", action="store_true")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--rating-games", type=int, default=6)
    parser.add_argument("--selfplay-games", type=int, default=8)
    parser.add_argument("--max-plies", type=int, default=120)
    parser.add_argument("--training-data", type=Path, default=app_config.training_data_path)
    parser.add_argument("--model-output", type=Path, default=app_config.model_path)
    parser.add_argument("--train-model", action="store_true")
    args = parser.parse_args()

    snapshot_profile = load_engine_profile(args.snapshot) if args.snapshot.exists() else None
    if snapshot_profile is None and not args.take_snapshot:
        raise FileNotFoundError(
            f"Snapshot profile {args.snapshot} does not exist. Use --take-snapshot to create it first."
        )

    config = LabConfig(
        snapshot_path=args.snapshot,
        training_data_path=args.training_data,
        model_output_path=args.model_output,
        depth=args.depth,
        rating_games=args.rating_games,
        selfplay_games=args.selfplay_games,
        max_plies=args.max_plies,
        snapshot_name=args.snapshot_name,
        take_snapshot=args.take_snapshot,
        train_model=args.train_model,
    )
    summary = run_lab_cycle(config, snapshot_profile or load_engine_profile(args.snapshot))

    print(f"snapshot: {summary.snapshot_path}")
    print(f"history: {summary.history_path}")
    print(
        f"rating: score={summary.rating.score:.1f}/{summary.rating.games} "
        f"average={summary.rating.average:.3f} elo_diff={summary.rating.estimated_elo_diff:.1f}"
    )
    print(
        f"selfplay: games={summary.selfplay.games} samples={summary.selfplay.samples_written} "
        f"output={summary.selfplay.output_path}"
    )
    if summary.training is not None:
        print(
            f"training: epochs={summary.training.epochs} samples={summary.training.sample_count} "
            f"loss={summary.training.final_loss:.6f} output={summary.training.output_path}"
        )


if __name__ == "__main__":
    main()

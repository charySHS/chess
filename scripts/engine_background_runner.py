from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.config import AppConfig
from src.engine.background_runner import (
    RunnerConfig,
    RunnerPaths,
    read_pid,
    read_status,
    run_background_loop,
    start_background_runner,
    stop_background_runner,
)
from src.engine.lab import LabConfig
from src.engine.profile import default_snapshot_path


def add_shared_args(parser: argparse.ArgumentParser, app_config: AppConfig) -> None:
    parser.add_argument("--snapshot", type=Path, default=default_snapshot_path())
    parser.add_argument("--snapshot-name", type=str, default="baseline_v1")
    parser.add_argument("--take-snapshot", action="store_true")
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--rating-games", type=int, default=4)
    parser.add_argument("--selfplay-games", type=int, default=8)
    parser.add_argument("--max-plies", type=int, default=100)
    parser.add_argument("--training-data", type=Path, default=app_config.training_data_path)
    parser.add_argument("--model-output", type=Path, default=app_config.model_path)
    parser.add_argument("--train-model", action="store_true")
    parser.add_argument("--cycles", type=int, default=0, help="0 means run indefinitely.")
    parser.add_argument("--sleep-seconds", type=float, default=5.0)
    parser.add_argument("--snapshot-interval", type=int, default=0, help="Take a fresh snapshot every N cycles. 0 disables interval snapshots.")
    parser.add_argument("--pid-path", type=Path, default=RunnerPaths().pid_path)
    parser.add_argument("--status-path", type=Path, default=RunnerPaths().status_path)
    parser.add_argument("--log-path", type=Path, default=RunnerPaths().log_path)
    parser.add_argument("--history-path", type=Path, default=RunnerPaths().history_path)


def build_config(args) -> tuple[RunnerConfig, RunnerPaths]:
    lab = LabConfig(
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
    config = RunnerConfig(
        lab=lab,
        cycles=args.cycles,
        sleep_seconds=args.sleep_seconds,
        snapshot_interval=args.snapshot_interval,
    )
    paths = RunnerPaths(
        pid_path=args.pid_path,
        status_path=args.status_path,
        log_path=args.log_path,
        history_path=args.history_path,
    )
    return config, paths


def main() -> None:
    app_config = AppConfig()
    parser = argparse.ArgumentParser(description="Background runner for extensive NewChess training loops.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Start the background training loop.")
    add_shared_args(start_parser, app_config)

    run_parser = subparsers.add_parser("run", help="Run the loop in the foreground.")
    add_shared_args(run_parser, app_config)

    status_parser = subparsers.add_parser("status", help="Show runner status.")
    status_parser.add_argument("--pid-path", type=Path, default=RunnerPaths().pid_path)
    status_parser.add_argument("--status-path", type=Path, default=RunnerPaths().status_path)
    status_parser.add_argument("--log-path", type=Path, default=RunnerPaths().log_path)
    status_parser.add_argument("--history-path", type=Path, default=RunnerPaths().history_path)

    stop_parser = subparsers.add_parser("stop", help="Stop the background training loop.")
    stop_parser.add_argument("--pid-path", type=Path, default=RunnerPaths().pid_path)
    stop_parser.add_argument("--status-path", type=Path, default=RunnerPaths().status_path)
    stop_parser.add_argument("--log-path", type=Path, default=RunnerPaths().log_path)
    stop_parser.add_argument("--history-path", type=Path, default=RunnerPaths().history_path)

    args = parser.parse_args()

    if args.command == "status":
        paths = RunnerPaths(args.pid_path, args.status_path, args.log_path, args.history_path)
        payload = read_status(paths) or {"state": "unknown", "message": "No status file found"}
        pid = read_pid(paths)
        if pid is not None:
            payload["pid"] = pid
        print(json.dumps(payload, indent=2))
        return

    if args.command == "stop":
        paths = RunnerPaths(args.pid_path, args.status_path, args.log_path, args.history_path)
        stopped = stop_background_runner(paths)
        print("stop signal sent" if stopped else "runner not active")
        return

    config, paths = build_config(args)
    if args.command == "start":
        pid = start_background_runner(Path(__file__).resolve(), config, paths)
        print(f"background runner started with pid {pid}")
        print(f"log: {paths.log_path}")
        print(f"status: {paths.status_path}")
        return

    run_background_loop(config, paths)


if __name__ == "__main__":
    main()

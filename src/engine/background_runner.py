from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.engine.lab import LabConfig, LabSummary, run_lab_cycle
from src.engine.profile import current_engine_profile, load_engine_profile


@dataclass(frozen=True)
class RunnerPaths:
    pid_path: Path = Path("artifacts/engine_runner.pid")
    status_path: Path = Path("artifacts/engine_runner_status.json")
    log_path: Path = Path("artifacts/engine_runner.log")
    history_path: Path = Path("artifacts/engine_lab_history.jsonl")


@dataclass(frozen=True)
class RunnerConfig:
    lab: LabConfig
    cycles: int = 0
    sleep_seconds: float = 5.0
    snapshot_interval: int = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_status(paths: RunnerPaths, payload: dict[str, object]) -> None:
    paths.status_path.parent.mkdir(parents=True, exist_ok=True)
    paths.status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_status(paths: RunnerPaths) -> dict[str, object] | None:
    if not paths.status_path.exists():
        return None
    return json.loads(paths.status_path.read_text(encoding="utf-8"))


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_pid(paths: RunnerPaths) -> int | None:
    if not paths.pid_path.exists():
        return None
    try:
        return int(paths.pid_path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def write_pid(paths: RunnerPaths, pid: int) -> None:
    paths.pid_path.parent.mkdir(parents=True, exist_ok=True)
    paths.pid_path.write_text(str(pid), encoding="utf-8")


def clear_pid(paths: RunnerPaths) -> None:
    if paths.pid_path.exists():
        paths.pid_path.unlink()


def start_background_runner(script_path: Path, config: RunnerConfig, paths: RunnerPaths) -> int:
    existing_pid = read_pid(paths)
    if existing_pid is not None and _pid_is_alive(existing_pid):
        raise RuntimeError(f"Background runner already active with pid {existing_pid}")

    paths.log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = paths.log_path.open("a", encoding="utf-8")
    args = [
        sys.executable,
        str(script_path),
        "run",
        "--snapshot",
        str(config.lab.snapshot_path),
        "--snapshot-name",
        config.lab.snapshot_name,
        "--depth",
        str(config.lab.depth),
        "--rating-games",
        str(config.lab.rating_games),
        "--selfplay-games",
        str(config.lab.selfplay_games),
        "--max-plies",
        str(config.lab.max_plies),
        "--training-data",
        str(config.lab.training_data_path),
        "--model-output",
        str(config.lab.model_output_path),
        "--cycles",
        str(config.cycles),
        "--sleep-seconds",
        str(config.sleep_seconds),
        "--snapshot-interval",
        str(config.snapshot_interval),
        "--pid-path",
        str(paths.pid_path),
        "--status-path",
        str(paths.status_path),
        "--log-path",
        str(paths.log_path),
        "--history-path",
        str(paths.history_path),
    ]
    if config.lab.take_snapshot:
        args.append("--take-snapshot")
    if config.lab.train_model:
        args.append("--train-model")

    process = subprocess.Popen(
        args,
        stdout=log_handle,
        stderr=log_handle,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    write_pid(paths, process.pid)
    write_status(
        paths,
        {
            "state": "starting",
            "pid": process.pid,
            "started_at": _now(),
            "cycle": 0,
            "message": "Background runner starting",
            "config": {
                **asdict(config),
                "lab": {
                    **asdict(config.lab),
                    "snapshot_path": str(config.lab.snapshot_path),
                    "training_data_path": str(config.lab.training_data_path),
                    "model_output_path": str(config.lab.model_output_path),
                },
            },
        },
    )
    return process.pid


def stop_background_runner(paths: RunnerPaths) -> bool:
    pid = read_pid(paths)
    if pid is None or not _pid_is_alive(pid):
        clear_pid(paths)
        return False
    os.kill(pid, signal.SIGTERM)
    return True


def run_background_loop(config: RunnerConfig, paths: RunnerPaths) -> None:
    write_pid(paths, os.getpid())
    cycle = 0
    running = True

    def handle_term(signum, frame) -> None:  # pragma: no cover - signal path
        nonlocal running
        running = False
        write_status(
            paths,
            {
                "state": "stopping",
                "pid": os.getpid(),
                "cycle": cycle,
                "updated_at": _now(),
                "message": f"Received signal {signum}, stopping after current cycle",
            },
        )

    signal.signal(signal.SIGTERM, handle_term)
    signal.signal(signal.SIGINT, handle_term)

    try:
        while running and (config.cycles <= 0 or cycle < config.cycles):
            cycle += 1
            take_snapshot = config.lab.take_snapshot or (
                config.snapshot_interval > 0 and (cycle == 1 or cycle % config.snapshot_interval == 0)
            )
            cycle_lab = LabConfig(
                snapshot_path=config.lab.snapshot_path,
                training_data_path=config.lab.training_data_path,
                model_output_path=config.lab.model_output_path,
                depth=config.lab.depth,
                rating_games=config.lab.rating_games,
                selfplay_games=config.lab.selfplay_games,
                max_plies=config.lab.max_plies,
                snapshot_name=config.lab.snapshot_name,
                take_snapshot=take_snapshot,
                train_model=config.lab.train_model,
            )
            snapshot_profile = (
                load_engine_profile(cycle_lab.snapshot_path)
                if cycle_lab.snapshot_path.exists()
                else current_engine_profile("bootstrap")
            )
            write_status(
                paths,
                {
                    "state": "running",
                    "pid": os.getpid(),
                    "cycle": cycle,
                    "updated_at": _now(),
                    "message": f"Starting cycle {cycle}",
                },
            )

            latest_message = ""

            def progress(message: str) -> None:
                nonlocal latest_message
                latest_message = message
                write_status(
                    paths,
                    {
                        "state": "running",
                        "pid": os.getpid(),
                        "cycle": cycle,
                        "updated_at": _now(),
                        "message": message,
                    },
                )

            summary = run_lab_cycle(
                cycle_lab,
                snapshot_profile,
                progress=progress,
                history_path=paths.history_path,
            )
            _write_cycle_summary(paths, cycle, summary, latest_message or "Cycle complete")

            if not running or (config.cycles > 0 and cycle >= config.cycles):
                break
            time.sleep(config.sleep_seconds)
    finally:
        write_status(
            paths,
            {
                "state": "stopped",
                "pid": os.getpid(),
                "cycle": cycle,
                "updated_at": _now(),
                "message": "Background runner stopped",
            },
        )
        clear_pid(paths)


def _write_cycle_summary(paths: RunnerPaths, cycle: int, summary: LabSummary, message: str) -> None:
    write_status(
        paths,
        {
            "state": "idle",
            "pid": os.getpid(),
            "cycle": cycle,
            "updated_at": _now(),
            "message": message,
            "snapshot_path": str(summary.snapshot_path),
            "history_path": str(summary.history_path),
            "rating": asdict(summary.rating),
            "selfplay": {
                **asdict(summary.selfplay),
                "output_path": str(summary.selfplay.output_path),
            },
            "training": None
            if summary.training is None
            else {
                **asdict(summary.training),
                "output_path": str(summary.training.output_path),
            },
        },
    )

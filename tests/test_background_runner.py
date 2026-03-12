from __future__ import annotations

from src.engine.background_runner import RunnerConfig, RunnerPaths, read_status, run_background_loop
from src.engine.lab import LabConfig, save_snapshot


def test_background_runner_single_cycle_updates_status_and_history(tmp_path) -> None:
    snapshot_path = tmp_path / "snapshot.json"
    save_snapshot(snapshot_path, "runner_snapshot")

    paths = RunnerPaths(
        pid_path=tmp_path / "runner.pid",
        status_path=tmp_path / "runner_status.json",
        log_path=tmp_path / "runner.log",
        history_path=tmp_path / "runner_history.jsonl",
    )
    config = RunnerConfig(
        lab=LabConfig(
            snapshot_path=snapshot_path,
            training_data_path=tmp_path / "selfplay.jsonl",
            model_output_path=tmp_path / "value_network.npz",
            depth=1,
            rating_games=1,
            selfplay_games=1,
            max_plies=10,
            promote_snapshot_after_batch=True,
            train_model=False,
        ),
        cycles=1,
        sleep_seconds=0.0,
    )

    run_background_loop(config, paths)

    status = read_status(paths)
    assert status is not None
    assert status["state"] == "stopped"
    assert paths.history_path.exists()
    assert not paths.pid_path.exists()

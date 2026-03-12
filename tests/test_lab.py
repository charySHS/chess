from __future__ import annotations

from src.engine.lab import LabConfig, load_history_entries, run_lab_cycle, save_snapshot
from src.engine.profile import load_engine_profile


def test_lab_cycle_generates_samples(tmp_path) -> None:
    snapshot_path = tmp_path / "snapshot.json"
    training_path = tmp_path / "selfplay.jsonl"
    model_path = tmp_path / "value_network.npz"
    save_snapshot(snapshot_path, "test_snapshot")

    summary = run_lab_cycle(
        LabConfig(
            snapshot_path=snapshot_path,
            training_data_path=training_path,
            model_output_path=model_path,
            depth=1,
            rating_games=2,
            selfplay_games=1,
            max_plies=20,
            take_snapshot=False,
            train_model=False,
        ),
        load_engine_profile(snapshot_path),
        history_path=tmp_path / "history.jsonl",
    )

    assert summary.rating.games == 2
    assert summary.selfplay.samples_written >= 0
    assert training_path.exists()
    assert summary.history_path.exists()
    assert len(load_history_entries(summary.history_path)) == 1


def test_lab_cycle_emits_progress_messages(tmp_path) -> None:
    snapshot_path = tmp_path / "snapshot.json"
    training_path = tmp_path / "selfplay.jsonl"
    save_snapshot(snapshot_path, "test_snapshot")
    messages: list[str] = []

    run_lab_cycle(
        LabConfig(
            snapshot_path=snapshot_path,
            training_data_path=training_path,
            model_output_path=tmp_path / "value_network.npz",
            depth=1,
            rating_games=1,
            selfplay_games=1,
            max_plies=12,
            take_snapshot=False,
            train_model=False,
        ),
        load_engine_profile(snapshot_path),
        progress=messages.append,
        history_path=tmp_path / "history.jsonl",
    )

    assert any("Rating game" in message for message in messages)
    assert any("Self-play complete" in message for message in messages)

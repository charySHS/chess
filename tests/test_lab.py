from __future__ import annotations

import json
from src.engine.lab import LabConfig, load_history_entries, run_lab_cycle, save_snapshot
from src.engine.profile import load_engine_profile
from src.nn.encoder import ENCODED_SIZE
from src.nn.model import NetworkConfig, ValueNetwork


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
            promote_snapshot_after_batch=True,
            train_model=False,
        ),
        load_engine_profile(snapshot_path),
        history_path=tmp_path / "history.jsonl",
    )

    assert summary.rating.games == 2
    assert summary.selfplay.samples_written >= 0
    assert training_path.exists()
    assert summary.history_path.exists()
    assert summary.snapshot_path.name == "snapshot_v1.json" or summary.snapshot_path.name.startswith("snapshot_v")
    history = load_history_entries(summary.history_path)
    assert len(history) == 1
    assert history[0].promote_snapshot_after_batch is True
    assert training_path.read_text(encoding="utf-8") != ""


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
            promote_snapshot_after_batch=True,
            train_model=False,
        ),
        load_engine_profile(snapshot_path),
        progress=messages.append,
        history_path=tmp_path / "history.jsonl",
    )

    assert any("Rating game" in message for message in messages)
    assert any("Self-play complete" in message for message in messages)
    assert any("Promoted current engine snapshot" in message for message in messages)


def test_lab_cycle_freezes_snapshot_model_and_learns_from_rating_matches(tmp_path) -> None:
    snapshot_path = tmp_path / "snapshot.json"
    training_path = tmp_path / "matches.jsonl"
    model_path = tmp_path / "value_network.npz"
    ValueNetwork(NetworkConfig(input_size=ENCODED_SIZE, hidden_sizes=(32,))).save(model_path)
    save_snapshot(snapshot_path, "test_snapshot", model_source_path=model_path)

    summary = run_lab_cycle(
        LabConfig(
            snapshot_path=snapshot_path,
            training_data_path=training_path,
            model_output_path=model_path,
            depth=1,
            rating_games=1,
            selfplay_games=0,
            max_plies=8,
            take_snapshot=False,
            promote_snapshot_after_batch=True,
            train_model=False,
            learn_from_rating_matches=True,
        ),
        load_engine_profile(snapshot_path),
        history_path=tmp_path / "history.jsonl",
    )

    history = load_history_entries(summary.history_path)
    lines = [json.loads(line) for line in training_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert summary.snapshot_model_path is not None
    assert summary.snapshot_model_path.exists()
    assert len(lines) > 0
    assert history[0].snapshot_model_path is not None
    assert history[0].learn_from_rating_matches is True

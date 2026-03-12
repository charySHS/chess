from __future__ import annotations

from pathlib import Path

from src.chess_core import Board
from src.nn.dataset import TrainingSample, append_samples, augment_with_mirrors
from src.nn.encoder import ENCODED_SIZE, CASTLING_OFFSET, EN_PASSANT_OFFSET, encode_board, mirror_encoded_features
from src.nn.infer import NeuralEvaluator
from src.nn.model import NetworkConfig, ValueNetwork
from src.nn.trainer import TrainerConfig, train_value_network


def test_encoder_uses_expanded_feature_size() -> None:
    encoded = encode_board(Board())
    assert encoded.shape == (ENCODED_SIZE,)


def test_value_network_save_load_preserves_input_size(tmp_path: Path) -> None:
    path = tmp_path / "model.npz"
    network = ValueNetwork(NetworkConfig(input_size=ENCODED_SIZE, hidden_sizes=(64, 32)))
    network.save(path)

    loaded = ValueNetwork.load(path)

    assert loaded.config.input_size == ENCODED_SIZE
    assert loaded.config.hidden_sizes == (64, 32)


def test_value_network_loads_legacy_input_size(tmp_path: Path) -> None:
    path = tmp_path / "legacy_model.npz"
    network = ValueNetwork(NetworkConfig(input_size=128, hidden_sizes=(16,)))
    payload = {f"w{index}": weight for index, weight in enumerate(network.weights)}
    payload.update({f"b{index}": bias for index, bias in enumerate(network.biases)})
    payload["hidden_sizes"] = [16]
    payload["learning_rate"] = [network.config.learning_rate]
    import numpy as np

    np.savez(path, **payload)

    loaded = ValueNetwork.load(path)

    assert loaded.config.input_size == 128


def test_mirror_encoded_features_swaps_castling_and_en_passant() -> None:
    board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq d6 0 1")
    encoded = encode_board(board)
    mirrored = mirror_encoded_features(encoded)

    assert mirrored[CASTLING_OFFSET] == encoded[CASTLING_OFFSET + 1]
    assert mirrored[CASTLING_OFFSET + 1] == encoded[CASTLING_OFFSET]
    assert mirrored[CASTLING_OFFSET + 2] == encoded[CASTLING_OFFSET + 3]
    assert mirrored[CASTLING_OFFSET + 3] == encoded[CASTLING_OFFSET + 2]
    assert mirrored[EN_PASSANT_OFFSET + 20] == 1.0


def test_augment_with_mirrors_doubles_dataset() -> None:
    encoded = encode_board(Board()).reshape(1, -1)
    import numpy as np

    targets = np.asarray([[0.25]], dtype=np.float32)
    x_augmented, y_augmented = augment_with_mirrors(encoded, targets)

    assert x_augmented.shape[0] == 2
    assert y_augmented.shape[0] == 2


def test_train_value_network_returns_validation_metric(tmp_path: Path) -> None:
    dataset_path = tmp_path / "samples.jsonl"
    output_path = tmp_path / "trained_model.npz"
    append_samples(
        dataset_path,
        [
            TrainingSample(fen=Board().to_fen(), value_cp=0),
            TrainingSample(fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", value_cp=35),
            TrainingSample(fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", value_cp=12),
        ],
    )

    summary = train_value_network(
        dataset_path,
        output_path,
        trainer_config=TrainerConfig(epochs=2, batch_size=2, validation_split=0.34, patience=2),
    )

    assert output_path.exists()
    assert summary.sample_count == 3
    assert summary.best_validation_loss >= 0.0


def test_train_value_network_warm_starts_existing_model(tmp_path: Path) -> None:
    dataset_path = tmp_path / "samples.jsonl"
    output_path = tmp_path / "trained_model.npz"
    append_samples(
        dataset_path,
        [
            TrainingSample(fen=Board().to_fen(), value_cp=0),
            TrainingSample(fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", value_cp=12),
        ],
    )
    starter = ValueNetwork(NetworkConfig(input_size=ENCODED_SIZE, hidden_sizes=(32,)))
    starter.save(output_path)

    train_value_network(
        dataset_path,
        output_path,
        trainer_config=TrainerConfig(epochs=1, batch_size=1, validation_split=0.5, patience=1, warm_start=True),
    )
    loaded = ValueNetwork.load(output_path)

    assert loaded.config.hidden_sizes == (32,)


def test_neural_evaluator_adapts_legacy_input_size() -> None:
    network = ValueNetwork(NetworkConfig(input_size=128, hidden_sizes=(16,)))
    evaluator = NeuralEvaluator(network)

    value = evaluator.evaluate_board(Board())

    assert isinstance(value, float)

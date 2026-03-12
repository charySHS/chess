from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.nn.dataset import augment_with_mirrors, load_samples, samples_to_arrays
from src.nn.model import NetworkConfig, ValueNetwork

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    np = None


@dataclass(frozen=True)
class TrainerConfig:
    epochs: int = 28
    batch_size: int = 64
    shuffle: bool = True
    seed: int = 11
    validation_split: float = 0.1
    patience: int = 4
    augment_mirrors: bool = True
    warm_start: bool = True


@dataclass(frozen=True)
class TrainingSummary:
    epochs: int
    final_loss: float
    best_validation_loss: float
    sample_count: int
    output_path: Path


def train_value_network(
    dataset_path: Path,
    output_path: Path,
    trainer_config: TrainerConfig | None = None,
    network_config: NetworkConfig | None = None,
) -> TrainingSummary:
    config = trainer_config or TrainerConfig()
    samples = load_samples(dataset_path)
    if not samples:
        raise ValueError(f"No training samples found at {dataset_path}")

    x, y = samples_to_arrays(samples)
    if config.augment_mirrors:
        x, y = augment_with_mirrors(x, y)

    network = _load_or_create_network(output_path, network_config, warm_start=config.warm_start)
    rng = np.random.default_rng(config.seed)
    final_loss = 0.0
    best_validation_loss = float("inf")
    best_weights = [weight.copy() for weight in network.weights]
    best_biases = [bias.copy() for bias in network.biases]
    patience_left = config.patience

    sample_count = len(x)
    split_index = max(1, int(sample_count * (1.0 - config.validation_split)))
    if split_index >= sample_count:
        split_index = sample_count - 1
    if split_index <= 0:
        split_index = sample_count

    for _ in range(config.epochs):
        indices = np.arange(sample_count)
        if config.shuffle:
            rng.shuffle(indices)
        x_epoch = x[indices]
        y_epoch = y[indices]

        x_train = x_epoch[:split_index]
        y_train = y_epoch[:split_index]
        x_val = x_epoch[split_index:] if split_index < sample_count else x_epoch[:0]
        y_val = y_epoch[split_index:] if split_index < sample_count else y_epoch[:0]

        for start in range(0, len(x_train), config.batch_size):
            end = start + config.batch_size
            final_loss = network.train_batch(x_train[start:end], y_train[start:end])

        if len(x_val) > 0:
            predictions = network.predict(x_val)
            validation_loss = float(np.mean((predictions - y_val) ** 2))
        else:
            validation_loss = final_loss

        if validation_loss < best_validation_loss:
            best_validation_loss = validation_loss
            best_weights = [weight.copy() for weight in network.weights]
            best_biases = [bias.copy() for bias in network.biases]
            patience_left = config.patience
        else:
            patience_left -= 1
            if patience_left <= 0:
                break

    network.weights = best_weights
    network.biases = best_biases

    network.save(output_path)
    return TrainingSummary(
        epochs=config.epochs,
        final_loss=final_loss,
        best_validation_loss=best_validation_loss,
        sample_count=len(samples),
        output_path=output_path,
    )


def _load_or_create_network(output_path: Path, network_config: NetworkConfig | None, warm_start: bool) -> ValueNetwork:
    if warm_start and output_path.exists():
        try:
            return ValueNetwork.load(output_path)
        except Exception:
            pass
    return ValueNetwork(network_config)

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.nn.dataset import load_samples, samples_to_arrays
from src.nn.model import NetworkConfig, ValueNetwork

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    np = None


@dataclass(frozen=True)
class TrainerConfig:
    epochs: int = 20
    batch_size: int = 64
    shuffle: bool = True
    seed: int = 11


@dataclass(frozen=True)
class TrainingSummary:
    epochs: int
    final_loss: float
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
    network = ValueNetwork(network_config)
    rng = np.random.default_rng(config.seed)
    final_loss = 0.0

    for _ in range(config.epochs):
        indices = np.arange(len(samples))
        if config.shuffle:
            rng.shuffle(indices)
        x_epoch = x[indices]
        y_epoch = y[indices]

        for start in range(0, len(samples), config.batch_size):
            end = start + config.batch_size
            final_loss = network.train_batch(x_epoch[start:end], y_epoch[start:end])

    network.save(output_path)
    return TrainingSummary(
        epochs=config.epochs,
        final_loss=final_loss,
        sample_count=len(samples),
        output_path=output_path,
    )

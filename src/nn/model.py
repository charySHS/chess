from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    np = None

from src.nn.encoder import ENCODED_SIZE, require_numpy


@dataclass(frozen=True)
class NetworkConfig:
    input_size: int = ENCODED_SIZE
    hidden_sizes: tuple[int, ...] = (256, 128)
    learning_rate: float = 0.001
    seed: int = 7


class ValueNetwork:
    def __init__(self, config: NetworkConfig | None = None) -> None:
        require_numpy()
        self.config = config or NetworkConfig()
        rng = np.random.default_rng(self.config.seed)
        layer_sizes = (self.config.input_size,) + self.config.hidden_sizes + (1,)
        self.weights = [rng.normal(0.0, 0.05, size=(layer_sizes[i], layer_sizes[i + 1])).astype(np.float32) for i in range(len(layer_sizes) - 1)]
        self.biases = [np.zeros((1, layer_sizes[i + 1]), dtype=np.float32) for i in range(len(layer_sizes) - 1)]

    def forward(self, x):
        activations = [x]
        pre_activations = []
        current = x
        for index, (weight, bias) in enumerate(zip(self.weights, self.biases, strict=True)):
            z = current @ weight + bias
            pre_activations.append(z)
            if index == len(self.weights) - 1:
                current = np.tanh(z)
            else:
                current = np.maximum(z, 0.0)
            activations.append(current)
        return activations, pre_activations

    def predict(self, x):
        activations, _ = self.forward(x)
        return activations[-1]

    def train_batch(self, x, y) -> float:
        activations, pre_activations = self.forward(x)
        predictions = activations[-1]
        batch_size = x.shape[0]
        loss = float(np.mean((predictions - y) ** 2))

        delta = (2.0 * (predictions - y) / batch_size) * (1.0 - predictions ** 2)
        grad_w: list = []
        grad_b: list = []

        for layer_index in reversed(range(len(self.weights))):
            grad_w.insert(0, activations[layer_index].T @ delta)
            grad_b.insert(0, np.sum(delta, axis=0, keepdims=True))
            if layer_index > 0:
                delta = (delta @ self.weights[layer_index].T) * (pre_activations[layer_index - 1] > 0)

        for index in range(len(self.weights)):
            self.weights[index] -= self.config.learning_rate * grad_w[index]
            self.biases[index] -= self.config.learning_rate * grad_b[index]
        return loss

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {f"w{index}": weight for index, weight in enumerate(self.weights)}
        payload.update({f"b{index}": bias for index, bias in enumerate(self.biases)})
        payload["hidden_sizes"] = np.asarray(self.config.hidden_sizes, dtype=np.int32)
        payload["learning_rate"] = np.asarray([self.config.learning_rate], dtype=np.float32)
        np.savez(path, **payload)

    @classmethod
    def load(cls, path: Path) -> ValueNetwork:
        require_numpy()
        data = np.load(path, allow_pickle=False)
        hidden_sizes = tuple(int(item) for item in data["hidden_sizes"])
        learning_rate = float(data["learning_rate"][0])
        network = cls(NetworkConfig(hidden_sizes=hidden_sizes, learning_rate=learning_rate))
        network.weights = [data[f"w{index}"] for index in range(len(hidden_sizes) + 1)]
        network.biases = [data[f"b{index}"] for index in range(len(hidden_sizes) + 1)]
        return network

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
    hidden_sizes: tuple[int, ...] = (512, 256, 128)
    learning_rate: float = 0.0007
    weight_decay: float = 0.0001
    gradient_clip: float = 1.0
    leak: float = 0.05
    seed: int = 7


class ValueNetwork:
    def __init__(self, config: NetworkConfig | None = None) -> None:
        require_numpy()
        self.config = config or NetworkConfig()
        rng = np.random.default_rng(self.config.seed)
        layer_sizes = (self.config.input_size,) + self.config.hidden_sizes + (1,)
        self.weights = []
        for i in range(len(layer_sizes) - 1):
            scale = np.sqrt(2.0 / max(1, layer_sizes[i]))
            self.weights.append(rng.normal(0.0, scale, size=(layer_sizes[i], layer_sizes[i + 1])).astype(np.float32))
        self.biases = [np.zeros((1, layer_sizes[i + 1]), dtype=np.float32) for i in range(len(layer_sizes) - 1)]
        self.m_weights = [np.zeros_like(weight) for weight in self.weights]
        self.v_weights = [np.zeros_like(weight) for weight in self.weights]
        self.m_biases = [np.zeros_like(bias) for bias in self.biases]
        self.v_biases = [np.zeros_like(bias) for bias in self.biases]
        self.steps = 0

    def forward(self, x):
        activations = [x]
        pre_activations = []
        current = x
        for index, (weight, bias) in enumerate(zip(self.weights, self.biases)):
            z = current @ weight + bias
            pre_activations.append(z)
            if index == len(self.weights) - 1:
                current = np.tanh(z)
            else:
                current = np.where(z > 0.0, z, self.config.leak * z)
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
            grad_w.insert(0, activations[layer_index].T @ delta + self.config.weight_decay * self.weights[layer_index])
            grad_b.insert(0, np.sum(delta, axis=0, keepdims=True))
            if layer_index > 0:
                slope = np.where(pre_activations[layer_index - 1] > 0.0, 1.0, self.config.leak)
                delta = (delta @ self.weights[layer_index].T) * slope

        total_norm = 0.0
        for gradient in grad_w + grad_b:
            total_norm += float(np.sum(gradient * gradient))
        total_norm = float(np.sqrt(total_norm))
        if total_norm > self.config.gradient_clip:
            scale = self.config.gradient_clip / max(total_norm, 1e-8)
            grad_w = [gradient * scale for gradient in grad_w]
            grad_b = [gradient * scale for gradient in grad_b]

        self.steps += 1
        beta1 = 0.9
        beta2 = 0.999
        epsilon = 1e-8
        for index in range(len(self.weights)):
            self.m_weights[index] = beta1 * self.m_weights[index] + (1.0 - beta1) * grad_w[index]
            self.v_weights[index] = beta2 * self.v_weights[index] + (1.0 - beta2) * (grad_w[index] ** 2)
            self.m_biases[index] = beta1 * self.m_biases[index] + (1.0 - beta1) * grad_b[index]
            self.v_biases[index] = beta2 * self.v_biases[index] + (1.0 - beta2) * (grad_b[index] ** 2)

            m_weight_hat = self.m_weights[index] / (1.0 - beta1 ** self.steps)
            v_weight_hat = self.v_weights[index] / (1.0 - beta2 ** self.steps)
            m_bias_hat = self.m_biases[index] / (1.0 - beta1 ** self.steps)
            v_bias_hat = self.v_biases[index] / (1.0 - beta2 ** self.steps)

            self.weights[index] -= self.config.learning_rate * m_weight_hat / (np.sqrt(v_weight_hat) + epsilon)
            self.biases[index] -= self.config.learning_rate * m_bias_hat / (np.sqrt(v_bias_hat) + epsilon)
        return loss

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {f"w{index}": weight for index, weight in enumerate(self.weights)}
        payload.update({f"b{index}": bias for index, bias in enumerate(self.biases)})
        payload["hidden_sizes"] = np.asarray(self.config.hidden_sizes, dtype=np.int32)
        payload["input_size"] = np.asarray([self.config.input_size], dtype=np.int32)
        payload["learning_rate"] = np.asarray([self.config.learning_rate], dtype=np.float32)
        payload["weight_decay"] = np.asarray([self.config.weight_decay], dtype=np.float32)
        payload["gradient_clip"] = np.asarray([self.config.gradient_clip], dtype=np.float32)
        payload["leak"] = np.asarray([self.config.leak], dtype=np.float32)
        payload["seed"] = np.asarray([self.config.seed], dtype=np.int32)
        np.savez(path, **payload)

    @classmethod
    def load(cls, path: Path) -> ValueNetwork:
        require_numpy()
        with np.load(path, allow_pickle=False) as data:
            hidden_sizes = tuple(int(item) for item in data["hidden_sizes"])
            learning_rate = float(data["learning_rate"][0])
            first_weight = data["w0"]
            input_size = int(data["input_size"][0]) if "input_size" in data else int(first_weight.shape[0])
            weight_decay = float(data["weight_decay"][0]) if "weight_decay" in data else 0.0
            gradient_clip = float(data["gradient_clip"][0]) if "gradient_clip" in data else 1.0
            leak = float(data["leak"][0]) if "leak" in data else 0.0
            seed = int(data["seed"][0]) if "seed" in data else 7
            network = cls(
                NetworkConfig(
                    input_size=input_size,
                    hidden_sizes=hidden_sizes,
                    learning_rate=learning_rate,
                    weight_decay=weight_decay,
                    gradient_clip=gradient_clip,
                    leak=leak,
                    seed=seed,
                )
            )
            network.weights = [data[f"w{index}"].copy() for index in range(len(hidden_sizes) + 1)]
            network.biases = [data[f"b{index}"].copy() for index in range(len(hidden_sizes) + 1)]
            network.m_weights = [np.zeros_like(weight) for weight in network.weights]
            network.v_weights = [np.zeros_like(weight) for weight in network.weights]
            network.m_biases = [np.zeros_like(bias) for bias in network.biases]
            network.v_biases = [np.zeros_like(bias) for bias in network.biases]
            network.steps = 0
            return network

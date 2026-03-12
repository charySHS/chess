from __future__ import annotations

from array import array
from math import pi, sin

import pygame


class AudioManager:
    def __init__(self) -> None:
        self.enabled = False
        self._rook_alert: pygame.mixer.Sound | None = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1)
            self.enabled = True
        except pygame.error:
            self.enabled = False

    def play_rook_alert(self) -> None:
        if not self.enabled:
            return
        if self._rook_alert is None:
            self._rook_alert = self._build_rook_alert()
        if self._rook_alert is not None:
            self._rook_alert.play()

    def _build_rook_alert(self) -> pygame.mixer.Sound | None:
        try:
            sample_rate = 22050
            segments = (
                (0.06, 392.0, 0.55),
                (0.08, 587.33, 0.65),
                (0.16, 783.99, 0.75),
            )
            samples = array("h")
            for duration, freq, amplitude in segments:
                total = int(sample_rate * duration)
                for index in range(total):
                    envelope = min(1.0, index / max(1, total // 8)) * (1.0 - index / max(1, total))
                    value = sin(2.0 * pi * freq * (index / sample_rate))
                    samples.append(int(32767 * amplitude * envelope * value))
            return pygame.mixer.Sound(buffer=samples.tobytes())
        except pygame.error:
            return None

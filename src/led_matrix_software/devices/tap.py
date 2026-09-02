"""Device wrapper that keeps a copy of the last written frame.

Used by tray mode to show a live thumbnail / preview of exactly what the LED
matrix is displaying, without touching the display code paths.
"""

import threading
from typing import Optional

import numpy as np

from .base import LEDDevice


class FrameTapDevice(LEDDevice):
    """Delegates to another device while caching the latest matrix buffer."""

    def __init__(self, device: LEDDevice):
        self._device = device
        self._lock = threading.Lock()
        self._latest: Optional[np.ndarray] = None
        self.frame_count = 0

    @property
    def device(self) -> LEDDevice:
        """The wrapped device."""
        return self._device

    def write(self, matrix_buffer: np.ndarray) -> None:
        with self._lock:
            self._latest = matrix_buffer.copy()
            self.frame_count += 1
        self._device.write(matrix_buffer)

    def latest_frame(self) -> Optional[np.ndarray]:
        """Return a copy of the most recent matrix buffer (or None)."""
        with self._lock:
            return None if self._latest is None else self._latest.copy()

    def close(self) -> None:
        self._device.close()

    def __getattr__(self, name):
        # Forward device specific helpers (save_video, port, ...).
        return getattr(self._device, name)


def matrix_to_pixels(matrix_buffer: np.ndarray, width: int = 128, height: int = 16) -> np.ndarray:
    """Unpack a uint16 [8][16] matrix buffer into a bool array [height][width]."""
    pixels = np.zeros((height, width), dtype=bool)
    for x in range(width):
        col_idx = x // 16
        bit_idx = x % 16
        for y in range(height):
            pixels[y, x] = bool((int(matrix_buffer[col_idx][y]) >> (15 - bit_idx)) & 1)
    return pixels

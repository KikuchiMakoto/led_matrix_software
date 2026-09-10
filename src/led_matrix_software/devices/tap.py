"""Device wrapper that keeps a copy of the last written frame.

Used by tray mode to show a live thumbnail / preview of exactly what the LED
matrix is displaying, without touching the display code paths.
"""

import threading

import numpy as np

from .base import LEDDevice


class FrameTapDevice(LEDDevice):
    """Delegates to another device while caching the latest matrix buffer."""

    def __init__(self, device: LEDDevice):
        self._device = device
        self._lock = threading.Lock()
        self._latest: np.ndarray | None = None
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

    def write_grayscale(
        self, gray: np.ndarray, bits: int = 8, gamma: float = 2.2, gain: float = 1.0
    ) -> None:
        """Cache the grayscale frame and delegate (tray thumbnail support)."""
        with self._lock:
            h, w = gray.shape[:2]
            img = np.zeros((16, 128), dtype=np.uint8)
            vh, vw = min(h, 16), min(w, 128)
            if vh > 0 and vw > 0:
                img[:vh, :vw] = np.clip(gray[:vh, :vw], 0, 255)
            self._latest = img
            self.frame_count += 1
        self._device.write_grayscale(gray, bits=bits, gamma=gamma, gain=gain)

    def latest_frame(self) -> np.ndarray | None:
        """Return a copy of the most recent frame (or None)."""
        with self._lock:
            return None if self._latest is None else self._latest.copy()

    def close(self) -> None:
        self._device.close()

    def __getattr__(self, name):
        # Forward device specific helpers (save_video, port, ...).
        return getattr(self._device, name)


def matrix_to_pixels(matrix_buffer: np.ndarray, width: int = 128, height: int = 16) -> np.ndarray:
    """Unpack a uint16 [8][16] matrix buffer into a bool array [height][width]."""
    from ..matrix import matrix_buffer_to_image

    img = matrix_buffer_to_image(matrix_buffer)
    return img[:height, :width] > 0

"""Headless emulator device for AI-driven development.

No human-readable output, no screen clearing, no per-frame rendering cost.
An AI agent drives this device exactly like hardware and asserts on the
captured state:

- ``latest_frame``: current 16x128 uint8 image (0..255)
- ``frame_count``: total frames received
- ``fps()``: measured receive rate over a sliding window
- ``jitter_ms()``: stddev of inter-frame intervals (ms)
- ``history``: optional bounded deque of past frames
- ``save_png(path)``: dump latest frame for offline inspection
"""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path

import numpy as np


class AIEmulatorDevice:
    """In-memory LED matrix for automated verification."""

    WIDTH = 128
    HEIGHT = 16

    def __init__(self, history_len: int = 0, stats_window: int = 120) -> None:
        """
        Args:
            history_len: keep this many past frames (0 = latest only)
            stats_window: intervals kept for fps/jitter stats
        """
        self._frame = np.zeros((self.HEIGHT, self.WIDTH), dtype=np.uint8)
        self.frame_count = 0
        self._intervals: deque[float] = deque(maxlen=stats_window)
        self._last_t: float | None = None
        self.history: deque[np.ndarray] = deque(maxlen=history_len or None)
        self._keep_history = history_len > 0

    # -- LEDDevice interface ------------------------------------------------

    def write(self, matrix_buffer: np.ndarray) -> None:
        """Capture 1-bit [8][16] uint16 buffer as 16x128 binary image."""
        from ..matrix import matrix_buffer_to_image

        self._store(matrix_buffer_to_image(matrix_buffer))

    def write_grayscale(
        self,
        gray: np.ndarray,
        bits: int = 8,
        gamma: float = 2.2,
        gain: float = 1.0,
    ) -> None:
        """Capture grayscale image with the same tone curve as hardware path."""
        from ..matrix import gamma_lut

        h, w = gray.shape[:2]
        target = np.zeros((self.HEIGHT, self.WIDTH), dtype=np.uint8)
        vh, vw = min(h, self.HEIGHT), min(w, self.WIDTH)
        if vh > 0 and vw > 0:
            target[:vh, :vw] = np.clip(gray[:vh, :vw], 0, 255)
        corrected = np.clip(
            gamma_lut(gamma)[target].astype(np.float32) * gain, 0, 255
        ).astype(np.uint8)
        corrected = np.where((target > 0) & (corrected == 0), 1, corrected)
        self._store(corrected)

    def close(self) -> None:
        """No resources to release."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # -- AI inspection API ----------------------------------------------------

    @property
    def latest_frame(self) -> np.ndarray:
        """Current frame (16x128 uint8). Returns a copy."""
        return self._frame.copy()

    def fps(self) -> float:
        """Mean receive rate over the stats window (0 if <2 samples)."""
        if len(self._intervals) < 2:
            return 0.0
        return 1.0 / (sum(self._intervals) / len(self._intervals))

    def jitter_ms(self) -> float:
        """Stddev of inter-frame intervals in ms (0 if <3 samples)."""
        if len(self._intervals) < 3:
            return 0.0
        arr = np.asarray(self._intervals, dtype=np.float64)
        return float(arr.std() * 1000.0)

    def reset_stats(self) -> None:
        """Clear counters, timing stats, and history."""
        self.frame_count = 0
        self._intervals.clear()
        self._last_t = None
        self.history.clear()
        self._frame.fill(0)

    def save_png(self, path: str | Path) -> Path:
        """Dump latest frame as a grayscale PNG for offline inspection."""
        import cv2

        out = Path(path)
        cv2.imwrite(str(out), self._frame)
        return out

    # -- internals --------------------------------------------------------------

    def _store(self, img: np.ndarray) -> None:
        now = time.perf_counter()
        if self._last_t is not None:
            self._intervals.append(now - self._last_t)
        self._last_t = now
        self._frame = img
        self.frame_count += 1
        if self._keep_history:
            self.history.append(img.copy())

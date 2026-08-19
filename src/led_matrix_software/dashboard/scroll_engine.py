"""ScrollEngine: 128x16 表示バッファ + カラム FIFO による 2 段バッファスクロール.

The display buffer is exactly the LED matrix size (16 rows x 128 cols).
A column FIFO feeds new content from the right side; each tick shifts the
buffer one column to the left. Padding columns are pushed first and last so
text enters and exits smoothly. Pushing 128 columns of zero padding at idle
clears any leftover text without special handling.

The text-enqueue path iterates character by character. A placeholder
character in the text can be substituted with a hand-drawn 16x16 bitmap by
passing ``icon_overrides`` -- this is the infrastructure for future weather
or train icons even when the default dashboard mode renders plain text.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np


@dataclass
class Column:
    """Single-column payload pushed into the FIFO.

    data: 16-pixel column (values 0 / 255)
    is_alert: when True the display loop may flip the polarity for flashing
    """

    data: np.ndarray
    is_alert: bool = False


class ScrollEngine:
    """Two-stage buffer driver for a 16-row LED matrix."""

    WIDTH = 128
    HEIGHT = 16
    PAD_COLUMNS = WIDTH  # one full screen-width of padding per push

    def __init__(self, font, *, width: int = WIDTH, height: int = HEIGHT) -> None:
        self.font = font
        self.width = width
        self.height = height
        self._buffer = np.zeros((height, width), dtype=np.uint8)
        self._fifo: deque[Column] = deque()
        self._output: Optional[Callable[[np.ndarray], None]] = None
        self._flash_counter = 0
        self._pad_image = self._load_pad_image()

    def _load_pad_image(self) -> Optional[np.ndarray]:
        """Return the font's inter-character pad image as a 16xN uint8 array."""
        try:
            import cv2

            pad_path = self.font.font_dir / "padding.bmp"
            img = cv2.imread(str(pad_path))
            if img is None:
                return None
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
            return binary
        except Exception:
            return None

    @property
    def buffer(self) -> np.ndarray:
        """Current LED state (height x width, values 0 or 255)."""
        return self._buffer

    def set_output(self, fn: Callable[[np.ndarray], None]) -> None:
        """Register a callback that receives the buffer on every step."""
        self._output = fn

    def has_pending(self) -> bool:
        return bool(self._fifo)

    def pending_count(self) -> int:
        return len(self._fifo)

    def peek_next(self) -> Column:
        """Return the next column without consuming it."""
        if not self._fifo:
            raise IndexError("FIFO is empty")
        return self._fifo[0]

    def enqueue_padding(self, screen_widths: int = 1) -> None:
        """Push one or more full screens of blank columns (clear / lead-in)."""
        zero_col = np.zeros(self.height, dtype=np.uint8)
        for _ in range(screen_widths * self.PAD_COLUMNS):
            self._fifo.append(Column(data=zero_col.copy()))

    def enqueue_text(
        self,
        text: str,
        *,
        leading_screen_widths: int = 1,
        trailing_screen_widths: int = 1,
        alert_tokens: Optional[list[str]] = None,
        icon_overrides: Optional[dict[str, np.ndarray]] = None,
    ) -> None:
        """Render text into columns and append them to the FIFO.

        Renders character by character so a placeholder character in ``text``
        can be substituted with a hand-drawn 16x16 icon from ``icon_overrides``.
        ``alert_tokens`` are substrings whose matching columns are flagged
        is_alert=True so the display loop can apply inverted-flash.
        """
        pad_chars = " " * (self.width // 8)
        padded = pad_chars * leading_screen_widths + text + pad_chars * trailing_screen_widths
        alert_flags = self._alert_char_mask(padded, alert_tokens or [])
        icon_overrides = icon_overrides or {}

        is_first = True
        for i, ch in enumerate(padded):
            char_is_alert = alert_flags[i]
            payload, width = self._char_payload(ch, icon_overrides)
            if payload is None:
                continue
            if not is_first:
                self._push_pad()
            for col in range(width):
                self._fifo.append(Column(data=payload[:, col].copy(), is_alert=char_is_alert))
            is_first = False

    def _char_payload(
        self, ch: str, icon_overrides: dict[str, np.ndarray]
    ) -> tuple[Optional[np.ndarray], int]:
        """Resolve a character to a (column-image, width) pair, or (None, 0)."""
        if ch in icon_overrides:
            icon = icon_overrides[ch]
            if icon.shape[0] != self.height:
                return (None, 0)
            return (icon, icon.shape[1])
        char_img = self.font.get_char_image(ch)
        if char_img is None:
            return (None, 0)
        if char_img.ndim == 3:
            char_img = char_img[:, :, 0]
        return (char_img, char_img.shape[1])

    def _push_pad(self) -> None:
        """Push the inter-character pad columns into the FIFO."""
        if self._pad_image is None:
            return
        for col in range(self._pad_image.shape[1]):
            self._fifo.append(Column(data=self._pad_image[:, col].copy(), is_alert=False))

    def step(self) -> np.ndarray:
        """Shift buffer left by one column, pull next column from FIFO if any."""
        self._buffer[:, :-1] = self._buffer[:, 1:]
        self._buffer[:, -1] = 0
        if self._fifo:
            col = self._fifo.popleft()
            payload = col.data
            if col.is_alert and (self._flash_counter % 2 == 1):
                payload = 255 - payload
            self._buffer[:, -1] = payload
            self._flash_counter += 1 if col.is_alert else 0
        return self._buffer

    def render_to(self, fn: Callable[[np.ndarray], None]) -> None:
        """Push the current buffer to an output callback (e.g. device.write)."""
        fn(self._buffer)

    def _alert_char_mask(self, padded_text: str, alert_tokens: list[str]) -> list[bool]:
        """Return per-character alert flags aligned with ``padded_text``."""
        flags = [False] * len(padded_text)
        if not alert_tokens:
            return flags
        for token in alert_tokens:
            start = 0
            while True:
                idx = padded_text.find(token, start)
                if idx < 0:
                    break
                for i in range(idx, min(idx + len(token), len(padded_text))):
                    flags[i] = True
                start = idx + len(token)
        return flags

"""Grayscale video playback for the 128x16 LED matrix.

Source is either a video file (mp4 etc.) or a camera (``cam:N``).
Frames are resized to 128x16 grayscale and sent as COBS bit-plane frames.
Pacing uses PreciseTicker (drops lag beyond 2 frames, no catch-up spiral).
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

WIDTH = 128
HEIGHT = 16

# Established reference tone (verified on real LED).
DEFAULT_GAMMA = 2.2
DEFAULT_GAIN = 110 / 255
DEFAULT_BITS = 8
DEFAULT_FPS = 30.0


def _open_source(src: str) -> tuple[cv2.VideoCapture, bool]:
    """Open video source. Returns (capture, is_camera)."""
    if src.startswith("cam:"):
        try:
            index = int(src.split(":", 1)[1])
        except ValueError:
            raise ValueError(f"bad camera source: {src!r} (use cam:N)")
        cap = cv2.VideoCapture(index)
        return cap, True
    cap = cv2.VideoCapture(src)
    return cap, False


def frame_to_gray(frame: np.ndarray, aspect: str = "crop", crop_y: int = 0) -> np.ndarray:
    """Convert any frame to 16x128 uint8 grayscale.

    Args:
        aspect: "crop" keeps source aspect by center-cropping to 8:1
            (plus crop_y offset, +down), "stretch" fills the panel.
    """
    if frame.ndim == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = frame.shape[:2]
    if aspect == "crop":
        target_ratio = WIDTH / HEIGHT  # 8:1
        if w / h > target_ratio:
            # Source wider than panel: crop width (rare).
            crop_w = int(h * target_ratio)
            x0 = max(0, (w - crop_w) // 2)
            frame = frame[:, x0 : x0 + crop_w]
        elif w / h < target_ratio:
            # Source taller than panel: crop height (usual).
            crop_h = max(1, int(w / target_ratio))
            y0 = (h - crop_h) // 2 + crop_y
            y0 = max(0, min(h - crop_h, y0))
            frame = frame[y0 : y0 + crop_h, :]
    if frame.shape[1] != WIDTH or frame.shape[0] != HEIGHT:
        frame = cv2.resize(frame, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)
    if frame.dtype != np.uint8:
        frame = np.clip(frame, 0, 255).astype(np.uint8)
    return frame


class VideoPlayer:
    """Pull frames from a source and push them to an LED device."""

    def __init__(
        self,
        device,
        src: str,
        *,
        fps: float = 0.0,
        bits: int = DEFAULT_BITS,
        gamma: float = DEFAULT_GAMMA,
        gain: float = DEFAULT_GAIN,
        loop: bool = False,
        aspect: str = "crop",
        crop_y: int = 0,
    ) -> None:
        from .protocol import MAX_BITS, MIN_BITS

        if not (MIN_BITS <= bits <= MAX_BITS):
            raise ValueError(f"bits must be {MIN_BITS}..{MAX_BITS}")
        if aspect not in ("crop", "stretch"):
            raise ValueError("aspect must be crop or stretch")
        self.device = device
        self.src = src
        self.fps = float(fps)
        self.bits = bits
        self.gamma = gamma
        self.gain = gain
        self.loop = loop
        self.aspect = aspect
        self.crop_y = crop_y

    def run(self, stop_event=None) -> int:
        """Play until source ends, loop flag exits, or stop_event. Returns frames sent."""
        from .timing import PreciseTicker

        cap, is_camera = _open_source(self.src)
        if not cap.isOpened():
            raise RuntimeError(f"cannot open video source: {self.src!r}")
        try:
            src_fps = cap.get(cv2.CAP_PROP_FPS)
            fps = self.fps or (src_fps if src_fps and src_fps > 0 else DEFAULT_FPS)
            if fps <= 0:
                fps = DEFAULT_FPS
            logger.info("Video %s at %.1ffps (%dbit)", self.src, fps, self.bits)
            print(f"Playing {self.src} at {fps:.1f}fps ({self.bits}bit)...")
            ticker = PreciseTicker(1.0 / fps)
            frames = 0
            dropped = 0
            while True:
                if stop_event is not None and stop_event.is_set():
                    break
                ok, frame = cap.read()
                if not ok:
                    if self.loop and not is_camera:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    break
                gray = frame_to_gray(frame, self.aspect, self.crop_y)
                try:
                    self.device.write_grayscale(
                        gray, bits=self.bits, gamma=self.gamma, gain=self.gain
                    )
                except Exception as e:
                    # Sustained streaming must survive a transient stall
                    # (e.g. USB write timeout): drop the frame and continue.
                    dropped += 1
                    if dropped <= 3 or dropped % 100 == 0:
                        logger.warning("Dropped video frame %d: %s", frames, e)
                    ticker.sleep_until_next()
                    continue
                frames += 1
                ticker.sleep_until_next()
            print(f"Video done ({frames} frames, {dropped} dropped).")
            return frames
        finally:
            cap.release()

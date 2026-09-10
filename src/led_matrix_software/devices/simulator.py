"""LED Matrix Simulator - Terminal and Image output"""

import io
import sys
from pathlib import Path

import cv2
import numpy as np

from .base import LEDDevice


class TerminalSimulator(LEDDevice):
    """Simulated LED matrix device with terminal output.

    Fast paths for animation: ANSI cursor-home instead of screen clear,
    vectorized buffer decode, and a shared renderer for 1-bit/grayscale.
    """

    # Density ramp for grayscale preview (10 steps)
    _RAMP = " .:-=+*#%@"
    _RAMP_ASCII = " .:-=+*#@@"
    _ANSI_HOME = "\x1b[H"
    _ANSI_CLEAR = "\x1b[2J"
    _ANSI_RED = "\x1b[31m"
    _ANSI_RESET = "\x1b[0m"

    def __init__(self, use_unicode: bool = True, color: bool = True,
                 show_stats: bool = True):
        """
        Initialize terminal simulator.

        Args:
            use_unicode: Use Unicode block characters for better display (default: True)
            color: Red LED-color output when attached to a TTY (default: True)
            show_stats: Show frame counter and fps in the header (default: True)
        """
        self.width = 128  # 8 columns * 16 bits
        self.height = 16
        self.use_unicode = use_unicode
        self.show_stats = show_stats
        self.frame_count = 0
        self._stdout = self._make_stdout()
        self._tty = self._console_available()
        self.color = bool(color) and self._tty
        self._first_draw = True
        self._last_t = None
        self._fps = 0.0

    @staticmethod
    def _console_available() -> bool:
        """False when detached from a console (background/tray mode)."""
        try:
            return bool(sys.stdout.isatty())
        except Exception:
            return False

    @staticmethod
    def _make_stdout() -> io.TextIOBase:
        """Return a stdout configured to emit UTF-8 on Windows consoles."""
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        return sys.stdout

    def write_grayscale(self, gray: np.ndarray, bits: int = 8, gamma: float = 2.2,
                        gain: float = 1.0) -> None:
        """
        Display grayscale image in terminal using a density ramp.

        Args:
            gray: uint8 array (16, 128)
        """
        from ..matrix import gamma_lut

        h, w = gray.shape[:2]
        target = np.zeros((self.height, self.width), dtype=np.uint8)
        vh, vw = min(h, self.height), min(w, self.width)
        if vh > 0 and vw > 0:
            target[:vh, :vw] = np.clip(gray[:vh, :vw], 0, 255)
        corrected = np.clip(
            gamma_lut(gamma)[target].astype(np.float32) * gain, 0, 255
        ).astype(np.uint8)
        self._render(corrected)

    def write(self, matrix_buffer: np.ndarray) -> None:
        """
        Display matrix buffer in terminal.

        Args:
            matrix_buffer: uint16 array [8][16]
        """
        from ..matrix import matrix_buffer_to_image

        self._render(matrix_buffer_to_image(matrix_buffer))

    def _render(self, img: np.ndarray) -> None:
        """Render a 16x128 uint8 image (shared by write/write_grayscale)."""
        import time

        now = time.perf_counter()
        if self._last_t is not None and now > self._last_t:
            dt = now - self._last_t
            if dt > 0:
                self._fps = 0.9 * self._fps + 0.1 * (1.0 / dt) if self._fps else 1.0 / dt
        self._last_t = now

        ramp = self._RAMP if self.use_unicode else self._RAMP_ASCII
        levels = len(ramp) - 1
        idx = (img.astype(np.uint16) * levels // 255).astype(np.int64)

        out = self._stdout
        parts = []
        if self._tty:
            # Cursor-home redraw (no clear = no flicker); full clear once.
            parts.append(self._ANSI_HOME + (self._ANSI_CLEAR if self._first_draw else ""))
            self._first_draw = False
        if self.show_stats:
            parts.append(
                f"=== LED Matrix Simulator "
                f"(Frame {self.frame_count}  {self._fps:.1f}fps) ===\n"
            )
        else:
            parts.append(f"=== LED Matrix Simulator (Frame {self.frame_count}) ===\n")
        parts.append("+" + "-" * self.width + "+\n")
        for y in range(self.height):
            row_chars = [ramp[i] for i in idx[y]]
            if self.color:
                # Paint lit cells red; keep spaces uncolored for clean logs.
                row = "|"
                for ch in row_chars:
                    row += f"{self._ANSI_RED}{ch}{self._ANSI_RESET}" if ch != " " else " "
                row += "|\n"
            else:
                row = "|" + "".join(row_chars) + "|\n"
            parts.append(row)
        parts.append("+" + "-" * self.width + "+\n")
        try:
            out.write("".join(parts))
            out.flush()
        except Exception:
            pass
        self.frame_count += 1

    def close(self) -> None:
        """No resources to close for terminal output"""


class ImageSimulator(LEDDevice):
    """Simulated LED matrix device with image file output"""

    def __init__(
        self, output_dir: str = "output", pixel_size: int = 10, save_individual_frames: bool = False
    ):
        """
        Initialize image simulator.

        Args:
            output_dir: Directory to save output images (default: 'output')
            pixel_size: Size of each LED pixel (default: 10)
            save_individual_frames: Save each frame as individual PNG (default: False)
        """
        self.width = 128  # 8 columns * 16 bits
        self.height = 16
        self.pixel_size = pixel_size
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.frame_count = 0
        self.frames = []
        self.save_individual_frames = save_individual_frames
        # Pre-rendered LED sprite (float32 BGR); stamped additively per frame.
        # Size tracks pixel_size so custom scales keep working.
        self._sprite_size = pixel_size + 1
        self._sprite = self._make_sprite(self._sprite_size)
        self._border_size = 20

    def write_grayscale(self, gray: np.ndarray, bits: int = 8, gamma: float = 2.2,
                        gain: float = 1.0) -> None:
        """
        Save grayscale image with brightness-scaled LED rendering.

        Args:
            gray: uint8 array (16, 128)
        """
        from ..matrix import gamma_lut

        h, w = gray.shape[:2]
        target = np.zeros((self.height, self.width), dtype=np.uint8)
        vh, vw = min(h, self.height), min(w, self.width)
        if vh > 0 and vw > 0:
            target[:vh, :vw] = np.clip(gray[:vh, :vw], 0, 255)
        corrected = np.clip(
            gamma_lut(gamma)[target].astype(np.float32) * gain, 0, 255
        ).astype(np.uint8)

        ps = self.pixel_size
        canvas = self._new_canvas()
        ys, xs = np.nonzero(corrected)
        for y, x in zip(ys.tolist(), xs.tolist()):
            self._stamp(
                canvas,
                x * ps + ps // 2,
                y * ps + ps // 2 + self._border_size,
                int(corrected[y, x]),
            )
        self._finish_frame(canvas)

    def write(self, matrix_buffer: np.ndarray) -> None:
        """
        Save matrix buffer as image file with LED-like rendering.

        Args:
            matrix_buffer: uint16 array [8][16]
        """
        from ..matrix import matrix_buffer_to_image

        lit = matrix_buffer_to_image(matrix_buffer) > 0

        ps = self.pixel_size
        canvas = self._new_canvas()
        ys, xs = np.nonzero(lit)
        for y, x in zip(ys.tolist(), xs.tolist()):
            self._stamp(
                canvas, x * ps + ps // 2, y * ps + ps // 2 + self._border_size, 255
            )

        # Always keep in memory for potential video/static output
        self._finish_frame(canvas)

    @staticmethod
    def _make_sprite(size: int) -> np.ndarray:
        """Render one red LED glow sprite (float32 BGR) of size SxS."""
        side = size
        center = size // 2
        sprite = np.zeros((side, side, 3), dtype=np.uint8)
        # Radii scale with sprite size (reference: pixel_size=10 -> r 5..1)
        k = size / 11.0
        cv2.circle(sprite, (center, center), max(1, round(5 * k)), (0, 0, 80), -1, cv2.LINE_AA)
        cv2.circle(sprite, (center, center), max(1, round(4 * k)), (0, 0, 150), -1, cv2.LINE_AA)
        cv2.circle(sprite, (center, center), max(1, round(3 * k)), (0, 0, 220), -1, cv2.LINE_AA)
        cv2.circle(sprite, (center, center), max(1, round(2 * k)), (0, 0, 255), -1, cv2.LINE_AA)
        cv2.circle(sprite, (center, center), 1, (40, 40, 255), -1, cv2.LINE_AA)
        return sprite.astype(np.float32)

    def _new_canvas(self) -> np.ndarray:
        """Float32 accumulator canvas (overlap adds, clipped on store)."""
        ps = self.pixel_size
        h = self.height * ps + self._border_size * 2
        w = self.width * ps
        return np.zeros((h, w, 3), dtype=np.float32)

    def _stamp(self, canvas: np.ndarray, cx: int, cy: int, level: int) -> None:
        """Additively stamp the LED sprite at canvas coords (edge-clipped)."""
        s = self._sprite_size
        half = s // 2
        x0, y0 = cx - half, cy - half
        x1, y1 = x0 + s, y0 + s
        sx0, sy0 = max(0, -x0), max(0, -y0)
        sx1, sy1 = s - max(0, x1 - canvas.shape[1]), s - max(0, y1 - canvas.shape[0])
        canvas[max(0, y0) : y1, max(0, x0) : x1] += (
            self._sprite[sy0:sy1, sx0:sx1] * (level / 255.0)
        )

    def _finish_frame(self, canvas: np.ndarray) -> None:
        """Clip accumulator to uint8, store frame, save PNG if requested."""
        img = np.clip(canvas, 0, 255).astype(np.uint8)
        if self.save_individual_frames:
            output_file = self.output_dir / f"frame_{self.frame_count:04d}.png"
            cv2.imwrite(str(output_file), img)
        self.frames.append(img)
        self.frame_count += 1

    def save_video(self, filename: str = "animation.mp4", fps: int = 30) -> None:
        """
        Save all frames as MP4 video.

        Args:
            filename: Output MP4 filename
            fps: Frames per second
        """
        if not self.frames:
            return

        output_path = self.output_dir / filename
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        height, width = self.frames[0].shape[:2]
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        for frame in self.frames:
            out.write(frame)

        out.release()
        print(f"Animation saved to {output_path}")

    def save_static_image(self, filename: str = "display.png") -> None:
        """
        Save the last frame as a static PNG image.

        Args:
            filename: Output PNG filename
        """
        if not self.frames:
            return

        output_path = self.output_dir / filename
        cv2.imwrite(str(output_path), self.frames[-1])
        print(f"Static image saved to {output_path}")

    def close(self) -> None:
        """Save output based on number of frames"""
        if not self.frames:
            return

        # If only one frame, save as static image
        if len(self.frames) == 1:
            self.save_static_image()
        # If multiple frames, save as video
        else:
            self.save_video()


# Alias for backward compatibility
SimulatorDevice = TerminalSimulator

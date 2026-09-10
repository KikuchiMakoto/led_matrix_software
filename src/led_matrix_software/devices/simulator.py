"""LED Matrix Simulator - Terminal and Image output"""

import os
import sys
import io
import numpy as np
import cv2
from pathlib import Path

from .base import LEDDevice


class TerminalSimulator(LEDDevice):
    """Simulated LED matrix device with terminal output"""

    def __init__(self, use_unicode: bool = True):
        """
        Initialize terminal simulator.

        Args:
            use_unicode: Use Unicode block characters for better display (default: True)
        """
        self.width = 128  # 8 columns * 16 bits
        self.height = 16
        self.use_unicode = use_unicode
        self.frame_count = 0
        self._stdout = self._make_stdout()
        self._can_clear = self._console_available()

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

    # Density ramp for grayscale preview (10 steps)
    _RAMP = " .:-=+*#%@"

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
        ramp = self._RAMP
        levels = len(ramp) - 1
        if self._can_clear:
            if os.name == "nt":
                os.system("cls")
            else:
                os.system("clear")
        out = self._stdout
        out.write(f"\n=== LED Matrix Simulator (Frame {self.frame_count}) ===\n")
        out.write("+" + "-" * self.width + "+\n")
        idx = (corrected.astype(np.uint16) * levels // 255).astype(np.int64)
        for y in range(self.height):
            out.write("|" + "".join(ramp[i] for i in idx[y]) + "|\n")
        out.write("+" + "-" * self.width + "+\n")
        try:
            out.flush()
        except Exception:
            pass
        self.frame_count += 1

    def write(self, matrix_buffer: np.ndarray) -> None:
        """
        Display matrix buffer in terminal.

        Args:
            matrix_buffer: uint16 array [8][16]
        """
        # Clear screen (skipped when there is no console, e.g. background mode)
        if self._can_clear:
            if os.name == "nt":  # Windows
                os.system("cls")
            else:  # Unix/Linux/Mac
                os.system("clear")

        out = self._stdout
        out.write(f"\n=== LED Matrix Simulator (Frame {self.frame_count}) ===\n")
        out.write("+" + "-" * self.width + "+\n")

        for y in range(self.height):
            row = "|"
            for x in range(self.width):
                col_idx = x // 16
                bit_idx = x % 16
                value = matrix_buffer[col_idx][y]
                is_on = (value >> (15 - bit_idx)) & 1

                if self.use_unicode:
                    row += "█" if is_on else " "
                else:
                    row += "#" if is_on else " "
            row += "|"
            out.write(row + "\n")

        out.write("+" + "-" * self.width + "+\n")
        try:
            out.flush()
        except Exception:
            pass
        self.frame_count += 1

    def close(self) -> None:
        """No resources to close for terminal output"""
        pass


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

        border_size = 20
        canvas_height = self.height * self.pixel_size + border_size * 2
        canvas_width = self.width * self.pixel_size
        img = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)

        for y in range(self.height):
            for x in range(self.width):
                level = int(corrected[y, x])
                if level > 0:
                    center_x = x * self.pixel_size + self.pixel_size // 2
                    center_y = y * self.pixel_size + self.pixel_size // 2 + border_size
                    self._draw_glowing_led(img, center_x, center_y, level)

        if self.save_individual_frames:
            output_file = self.output_dir / f"frame_{self.frame_count:04d}.png"
            cv2.imwrite(str(output_file), img)

        self.frames.append(img)
        self.frame_count += 1

    def write(self, matrix_buffer: np.ndarray) -> None:
        """
        Save matrix buffer as image file with LED-like rendering.

        Args:
            matrix_buffer: uint16 array [8][16]
        """
        # Add vertical border (top and bottom)
        border_size = 20
        canvas_height = self.height * self.pixel_size + border_size * 2
        canvas_width = self.width * self.pixel_size

        # Create black background
        img = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)

        # Draw each LED as a glowing circle
        for y in range(self.height):
            for x in range(self.width):
                col_idx = x // 16
                bit_idx = x % 16
                value = matrix_buffer[col_idx][y]
                is_on = (value >> (15 - bit_idx)) & 1

                if is_on:
                    # Calculate center position (with border offset)
                    center_x = x * self.pixel_size + self.pixel_size // 2
                    center_y = y * self.pixel_size + self.pixel_size // 2 + border_size

                    # Draw LED with glow effect
                    self._draw_glowing_led(img, center_x, center_y)

        # Save individual frame if requested
        if self.save_individual_frames:
            output_file = self.output_dir / f"frame_{self.frame_count:04d}.png"
            cv2.imwrite(str(output_file), img)

        # Always keep in memory for potential video/static output
        self.frames.append(img)
        self.frame_count += 1

    def _draw_glowing_led(self, img: np.ndarray, cx: int, cy: int,
                          level: int = 255) -> None:
        """
        Draw a glowing LED effect at the specified position.

        Args:
            img: Image to draw on
            cx: Center X coordinate
            cy: Center Y coordinate
            level: Brightness 0..255 (scales the red intensity)
        """
        k = max(0, min(255, int(level))) / 255.0

        def dim(v: int) -> int:
            return int(v * k)

        # LED appearance: red glowing circle, intensity-scaled
        cv2.circle(img, (cx, cy), 5, (0, 0, dim(80)), -1, cv2.LINE_AA)
        cv2.circle(img, (cx, cy), 4, (0, 0, dim(150)), -1, cv2.LINE_AA)
        cv2.circle(img, (cx, cy), 3, (0, 0, dim(220)), -1, cv2.LINE_AA)
        cv2.circle(img, (cx, cy), 2, (0, 0, dim(255)), -1, cv2.LINE_AA)
        cv2.circle(img, (cx, cy), 1, (dim(40), dim(40), dim(255)), -1, cv2.LINE_AA)

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

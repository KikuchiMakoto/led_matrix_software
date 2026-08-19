"""Chara Zenkaku font renderer"""

from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from .base import FontRenderer


class CharaZenkakuFont(FontRenderer):
    """Chara Zenkaku 16-pixel Japanese font renderer"""

    def __init__(self, font_dir: str = "./chara_zenkaku"):
        """
        Initialize Chara Zenkaku font renderer.

        Args:
            font_dir: Path to chara_zenkaku font directory
        """
        self.font_dir = Path(font_dir)
        self.x_offset = 50
        self.y_offset = 50
        self.x_step = 17
        self.y_step = 17
        self.char_width = 16
        self.char_height = 16

    def _find_char_position(self, char: str) -> Optional[Tuple[int, int]]:
        """
        Find character position in character map.

        Args:
            char: Single character

        Returns:
            (line, column) position or None if not found
        """
        txt_path = self.font_dir / "chara_zenkaku.txt"
        try:
            with open(txt_path, mode="r", encoding="utf-8") as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    if char in line:
                        return (i, line.index(char))
        except FileNotFoundError:
            return None
        return None

    def get_char_image(self, char: str) -> Optional[np.ndarray]:
        """
        Get image for a single character.

        Args:
            char: Single character

        Returns:
            Character image (16x16) or None if not found
        """
        pos = self._find_char_position(char)
        if pos is None:
            return None

        line, num = pos
        png_path = self.font_dir / "chara_zenkaku.png"

        try:
            img = cv2.imread(str(png_path))
            if img is None:
                return None

            x = self.x_offset + num * self.x_step
            y = self.y_offset + line * self.y_step
            char_img = img[y : y + self.char_height, x : x + self.char_width]

            return char_img
        except Exception:
            return None

    def render_string(self, text: str) -> np.ndarray:
        """
        Render text string to binary image.

        Args:
            text: Text to render

        Returns:
            Binary image (height=16, variable width)
        """
        merged_image = None
        padding = cv2.imread(str(self.font_dir / "padding.bmp"))

        for char in text:
            char_img = self.get_char_image(char)
            if char_img is None:
                continue

            if merged_image is None:
                merged_image = char_img
            else:
                merged_image = cv2.hconcat([merged_image, padding, char_img])

        if merged_image is None:
            # Return empty image if no characters were rendered
            return np.zeros((16, 0), dtype=np.uint8)

        # Convert to grayscale
        merged_image = cv2.cvtColor(merged_image, cv2.COLOR_BGR2GRAY)
        # Binarize
        _, merged_image = cv2.threshold(merged_image, 128, 255, cv2.THRESH_BINARY)

        return merged_image

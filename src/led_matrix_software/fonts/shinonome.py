"""Shinonome 16-pixel font renderer"""

import csv
import unicodedata
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .base import FontRenderer


class ShinonomeFont(FontRenderer):
    """Shinonome 16-pixel Japanese font renderer"""

    class CharacterMapping:
        """Character code mapping"""

        def __init__(self, ver: int, jisx: int, utf8: int):
            self.ver = ver
            self.jisx = jisx
            self.utf8 = utf8

    def __init__(self, font_dir: str = "./shinonome16-1.0.4"):
        """
        Initialize Shinonome font renderer.

        Args:
            font_dir: Path to shinonome font directory
        """
        self.font_dir = Path(font_dir)
        self.zenkaku_map = []
        self._load_character_map()

    def _load_character_map(self):
        """Load character code mapping from TSV file"""
        tsv_path = self.font_dir / "iso-2022-jp-2004-std.tsv"
        with open(tsv_path, mode="r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f, delimiter="\t")
            # Skip header (23 lines)
            for _ in range(23):
                next(reader)

            for cols in reader:
                try:
                    ver, jisx = cols[0].split("-")
                    utf8 = cols[1].split("+")[1]
                    char = self.CharacterMapping(int(ver), int(jisx, 16), int(utf8, 16))
                    self.zenkaku_map.append(char)
                except (IndexError, ValueError):
                    pass

    def _get_latin_image(self, char: str) -> Optional[np.ndarray]:
        """Get image for ASCII character"""
        try:
            ascii_code = int(char.encode("ascii")[0])
        except (UnicodeEncodeError, UnicodeDecodeError):
            return None

        target_string = "STARTCHAR " + format(ascii_code, "2x")
        next_string = "ENCODING " + format(ascii_code, "d")

        bdf_path = self.font_dir / "latin.bdf"
        with open(bdf_path, mode="r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith(target_string) and lines[i + 1].startswith(next_string):
                    ret = np.zeros((16, 8, 3), np.uint8)
                    for j in range(16):
                        line = lines[i + 6 + j]
                        for bit in range(8):
                            ret[j][bit] = [0, 0, 0] if line[bit] == "." else [255, 255, 255]
                    return ret
        return None

    def _get_hankaku_image(self, char: str) -> Optional[np.ndarray]:
        """Get image for half-width character"""
        try:
            sjis = int(char.encode("shift_jis")[0])
        except (UnicodeEncodeError, UnicodeDecodeError):
            return None

        target_string = "STARTCHAR   " + format(sjis, "2x")

        bdf_path = self.font_dir / "hankaku.bdf"
        with open(bdf_path, mode="r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith(target_string):
                    ret = np.zeros((16, 8, 3), np.uint8)
                    for j in range(16):
                        line = lines[i + 6 + j]
                        for bit in range(8):
                            ret[j][bit] = [0, 0, 0] if line[bit] == "." else [255, 255, 255]
                    return ret
        return None

    def _get_zenkaku_image(self, char: str) -> Optional[np.ndarray]:
        """Get image for full-width character"""
        jisx = None
        for c in self.zenkaku_map:
            if c.utf8 == ord(char):
                jisx = c.jisx
                break

        if jisx is None:
            return None

        target_string = "STARTCHAR " + format(jisx, "4x")

        bdf_path = self.font_dir / "zenkaku.bdf"
        with open(bdf_path, mode="r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith(target_string):
                    ret = np.zeros((16, 16, 3), np.uint8)
                    for j in range(16):
                        line = lines[i + 6 + j]
                        for bit in range(16):
                            ret[j][bit] = [0, 0, 0] if line[bit] == "." else [255, 255, 255]
                    return ret
        return None

    def get_char_image(self, char: str) -> Optional[np.ndarray]:
        """
        Get image for a single character based on its width type.

        Args:
            char: Single character

        Returns:
            Character image (16x8 or 16x16) or None if not found
        """
        width_type = unicodedata.east_asian_width(char)

        if width_type == "Na":  # Narrow (ASCII)
            return self._get_latin_image(char)
        elif width_type in ("F", "W"):  # Fullwidth or Wide
            return self._get_zenkaku_image(char)
        elif width_type == "H":  # Halfwidth
            return self._get_hankaku_image(char)

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

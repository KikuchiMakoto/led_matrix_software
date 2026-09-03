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
        self._utf8_to_jisx: dict[int, int] = {}
        self._glyph_cache: dict[str, Optional[np.ndarray]] = {}
        self._latin_lines: Optional[list[str]] = None
        self._hankaku_lines: Optional[list[str]] = None
        self._zenkaku_lines: Optional[list[str]] = None
        self._latin_index: dict[str, int] = {}
        self._hankaku_index: dict[str, int] = {}
        self._zenkaku_index: dict[str, int] = {}
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
                    ver_i = int(ver)
                    jisx_i = int(jisx, 16)
                    utf8_i = int(utf8, 16)
                    char = self.CharacterMapping(ver_i, jisx_i, utf8_i)
                    self.zenkaku_map.append(char)
                    self._utf8_to_jisx[utf8_i] = jisx_i
                except (IndexError, ValueError):
                    pass

    def _ensure_bdf_indexed(self, bdf_name: str) -> tuple[list[str], dict[str, int]]:
        """Lazily load BDF file once and build an index mapping startchar key to line offset."""
        if bdf_name == "latin":
            if self._latin_lines is None:
                self._latin_lines, self._latin_index = self._index_bdf("latin.bdf")
            return self._latin_lines, self._latin_index
        elif bdf_name == "hankaku":
            if self._hankaku_lines is None:
                self._hankaku_lines, self._hankaku_index = self._index_bdf("hankaku.bdf")
            return self._hankaku_lines, self._hankaku_index
        else:
            if self._zenkaku_lines is None:
                self._zenkaku_lines, self._zenkaku_index = self._index_bdf("zenkaku.bdf")
            return self._zenkaku_lines, self._zenkaku_index

    def _index_bdf(self, filename: str) -> tuple[list[str], dict[str, int]]:
        path = self.font_dir / filename
        idx: dict[str, int] = {}
        if not path.exists():
            return [], idx
        with open(path, mode="r", encoding="utf-8") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.startswith("STARTCHAR"):
                key = line[10:].strip().lower()
                idx[key] = i
        return lines, idx

    def _get_latin_image(self, char: str) -> Optional[np.ndarray]:
        """Get image for ASCII character"""
        try:
            ascii_code = int(char.encode("ascii")[0])
        except (UnicodeEncodeError, UnicodeDecodeError):
            return None

        key = format(ascii_code, "2x").strip().lower()
        lines, idx = self._ensure_bdf_indexed("latin")
        if key not in idx:
            return None
        i = idx[key]
        ret = np.zeros((16, 8, 3), np.uint8)
        for j in range(16):
            if i + 6 + j < len(lines):
                line = lines[i + 6 + j]
                for bit in range(min(8, len(line))):
                    ret[j][bit] = [0, 0, 0] if line[bit] == "." else [255, 255, 255]
        return ret

    def _get_hankaku_image(self, char: str) -> Optional[np.ndarray]:
        """Get image for half-width character"""
        try:
            sjis = int(char.encode("shift_jis")[0])
        except (UnicodeEncodeError, UnicodeDecodeError):
            return None

        key = format(sjis, "2x").strip().lower()
        lines, idx = self._ensure_bdf_indexed("hankaku")
        if key not in idx:
            return None
        i = idx[key]
        ret = np.zeros((16, 8, 3), np.uint8)
        for j in range(16):
            if i + 6 + j < len(lines):
                line = lines[i + 6 + j]
                for bit in range(min(8, len(line))):
                    ret[j][bit] = [0, 0, 0] if line[bit] == "." else [255, 255, 255]
        return ret

    def _get_zenkaku_image(self, char: str) -> Optional[np.ndarray]:
        """Get image for full-width character"""
        jisx = self._utf8_to_jisx.get(ord(char))
        if jisx is None:
            for c in self.zenkaku_map:
                if c.utf8 == ord(char):
                    jisx = c.jisx
                    break

        if jisx is None:
            return None

        key = format(jisx, "4x").strip().lower()
        lines, idx = self._ensure_bdf_indexed("zenkaku")
        if key not in idx:
            return None
        i = idx[key]
        ret = np.zeros((16, 16, 3), np.uint8)
        for j in range(16):
            if i + 6 + j < len(lines):
                line = lines[i + 6 + j]
                for bit in range(min(16, len(line))):
                    ret[j][bit] = [0, 0, 0] if line[bit] == "." else [255, 255, 255]
        return ret

    def get_char_image(self, char: str) -> Optional[np.ndarray]:
        """
        Get image for a single character based on its width type.

        Args:
            char: Single character

        Returns:
            Character image (16x8 or 16x16) or None if not found
        """
        if char in self._glyph_cache:
            cached = self._glyph_cache[char]
            return cached.copy() if cached is not None else None

        img: Optional[np.ndarray] = None
        width_type = unicodedata.east_asian_width(char)

        if width_type == "Na":  # Narrow (ASCII)
            img = self._get_latin_image(char)
        elif width_type in ("F", "W", "A"):  # Fullwidth, Wide, or Ambiguous (e.g. ℃)
            img = self._get_zenkaku_image(char)
            if img is None:
                img = self._get_latin_image(char) or self._get_hankaku_image(char)
        elif width_type == "H":  # Halfwidth
            img = self._get_hankaku_image(char)

        self._glyph_cache[char] = img
        return img.copy() if img is not None else None

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

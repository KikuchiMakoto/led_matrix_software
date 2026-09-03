"""Weather and train icons used as inline 16x16 bitmaps in dashboard text.

Two sources are consulted:

1. **Hard-coded fallback icons** (defined below) -- always available.
2. **External BMP files** in ``dashboard/icons/weather/`` -- loaded at import
   time. Drop a ``<key>.bmp`` there and it overrides the hard-coded icon for
   that key. Filename (without ``.bmp``) is the weather string key.

Each icon is a 16x16 ``numpy.ndarray`` with values 0 (off) / 255 (on). The
dashboard scroll engine substitutes a placeholder character with these
bitmaps via its ``icon_overrides`` parameter.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np


logger = logging.getLogger(__name__)

ICON_DIRS = [
    Path(__file__).parent / "icons" / "weather",
    Path(__file__).parent / "icons",
    Path.cwd() / "dashboard" / "icons" / "weather",
    Path.cwd() / "dashboard" / "icons",
]


def _bmp(rows: list[str]) -> np.ndarray:
    """Build a 16x16 uint8 array from 16 lines of 16 '#' / '.' characters."""
    if len(rows) != 16:
        raise ValueError(f"icon must have 16 rows, got {len(rows)}")
    out = np.zeros((16, 16), dtype=np.uint8)
    for y, row in enumerate(rows):
        if len(row) != 16:
            raise ValueError(f"icon row {y} must be 16 cols, got {len(row)}: {row!r}")
        for x, ch in enumerate(row):
            if ch == "#":
                out[y, x] = 255
            elif ch == ".":
                out[y, x] = 0
            else:
                raise ValueError(f"icon row {y} col {x}: unexpected {ch!r}")
    return out


# --- Hard-coded fallback icons (used when no BMP is provided) ---

# Sun with rays - placed on a 16x16 grid
ICON_SUNNY = _bmp(
    [
        ".......##.......",
        ".......##.......",
        "................",
        "...#...##...#...",
        "....#......#....",
        ".....#....#.....",
        "......####......",
        "######.##.######",
        "######.##.######",
        "......####......",
        ".....#....#.....",
        "....#......#....",
        "...#...##...#...",
        "................",
        ".......##.......",
        ".......##.......",
    ]
)

ICON_CLOUDY = _bmp(
    [
        "................",
        "................",
        "......####......",
        "....##....##....",
        "...#........#...",
        "..#..........#..",
        "..#..........#..",
        ".#............#.",
        ".##############.",
        ".##############.",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
    ]
)

ICON_RAIN = _bmp(
    [
        "................",
        "................",
        "................",
        ".....######.....",
        "...##......##...",
        "..#..........#..",
        ".#............#.",
        ".#............#.",
        "##############..",
        "##############..",
        "................",
        "...##...##...##.",
        "....#....#....#.",
        "...##...##...##.",
        "....#....#....#.",
        "................",
    ]
)

ICON_SNOW = _bmp(
    [
        "................",
        "................",
        "................",
        ".....######.....",
        "...##......##...",
        "..#..........#..",
        ".#............#.",
        ".#............#.",
        "##############..",
        "##############..",
        "................",
        "......#.#.......",
        ".......#........",
        "......#.#.......",
        "................",
        "................",
    ]
)

ICON_THUNDER = _bmp(
    [
        "................",
        "................",
        ".....######.....",
        "...##......##...",
        "..#..........#..",
        ".#............#.",
        ".#............#.",
        "##############..",
        "##############..",
        "................",
        ".......##.......",
        "......##........",
        ".....##.........",
        "....##..........",
        ".....##.........",
        "................",
    ]
)

ICON_TRAIN_OK = _bmp(
    [
        "................",
        "................",
        "..##############",
        "..#............#",
        "..#.####.####.#.",
        "..#.####.####.#.",
        "..#............#",
        "..#.####.####.#.",
        "..#............#",
        "..##############",
        "..#.#.######.#.#",
        "...#.#........#.",
        "................",
        "................",
        "................",
        "................",
    ]
)

ICON_TRAIN_DELAY = _bmp(
    [
        "................",
        "................",
        "..##############",
        "..#............#",
        "..#.####.####.#.",
        "..#.####.####.#.",
        "..#............#",
        "..#.####.####.#.",
        "..#............#",
        "..##############",
        "..#.#.######.#.#",
        "...#.#........#.",
        "................",
        ".....##.........",
        "......##........",
        ".......##.......",
    ]
)

ICON_TRAIN_UNKNOWN = _bmp(
    [
        "................",
        "................",
        "..##############",
        "..#............#",
        "..#.####.####.#.",
        "..#.####.####.#.",
        "..#............#",
        "..#.####.####.#.",
        "..#............#",
        "..##############",
        "..#.#.######.#.#",
        "...#.#........#.",
        "................",
        "......####......",
        ".....#....#.....",
        "................",
    ]
)


# Hardcoded fallback: keyword -> icon
HARDCODED_WEATHER_ICONS = {
    "晴": ICON_SUNNY,
    "晴れ": ICON_SUNNY,
    "曇": ICON_CLOUDY,
    "曇り": ICON_CLOUDY,
    "雨": ICON_RAIN,
    "雨時々曇": ICON_RAIN,
    "雨時々雪": ICON_RAIN,
    "雪": ICON_SNOW,
    "雷": ICON_THUNDER,
    "雷雨": ICON_THUNDER,
}

# Special placeholders for compound weather icon tokens
NOCHI_PLACEHOLDER = "\ue001"
TOKIDOKI_PLACEHOLDER = "\ue002"

# English filename aliases mapped to Japanese weather keys
WEATHER_ICON_ALIASES: dict[str, list[str]] = {
    "sunny": ["晴", "晴れ", "快晴"],
    "clear": ["晴", "晴れ", "快晴"],
    "cloudy": ["曇", "曇り"],
    "rain": ["雨", "小雨", "大雨", "雨時々曇", "雨時々雪"],
    "rainy": ["雨", "小雨", "大雨", "雨時々曇", "雨時々雪"],
    "snow": ["雪", "大雪", "みぞれ"],
    "snowy": ["雪", "大雪", "みぞれ"],
    "thunder": ["雷", "雷雨"],
    "storm": ["雷", "雷雨", "嵐"],
    "celsius": ["℃", "度"],
    "degree": ["℃", "度"],
    "nochi": [NOCHI_PLACEHOLDER, "のち"],
    "tokidoki": [TOKIDOKI_PLACEHOLDER, "時々", "ときどき", "一時"],
}

HARDCODED_TRAIN_ICONS = {
    "平常通り": ICON_TRAIN_OK,
    "平常": ICON_TRAIN_OK,
    "遅延": ICON_TRAIN_DELAY,
    "運転見合わせ": ICON_TRAIN_DELAY,
    "運転停止": ICON_TRAIN_DELAY,
    "取得失敗": ICON_TRAIN_UNKNOWN,
    "未取得": ICON_TRAIN_UNKNOWN,
}


def _load_external_bmp_icons(directory: Path) -> dict[str, np.ndarray]:
    """Load 16x16 monochrome BMP files from ``directory``.

    Filename (without extension) becomes the icon key. Files of wrong size
    or unreadable files are silently skipped (logged).

    Uses ``cv2.imdecode`` on raw bytes (rather than ``cv2.imread``) so that
    non-ASCII filenames work reliably on Windows where OpenCV's path
    encoding diverges from Python's UTF-8 paths.
    """
    icons: dict[str, np.ndarray] = {}
    if not directory.exists():
        return icons
    try:
        import cv2
    except ImportError:
        logger.warning("opencv-python not available; external BMP icons disabled")
        return icons

    for bmp_path in sorted(directory.glob("*.bmp")):
        try:
            raw = Path(bmp_path).read_bytes()
            arr = np.frombuffer(raw, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        except Exception as exc:
            logger.warning("Failed to load %s: %s", bmp_path, exc)
            continue
        if img is None:
            logger.warning("Failed to decode %s (cv2 returned None)", bmp_path)
            continue
        if img.shape[0] != 16 or img.shape[1] < 1 or img.shape[1] > 16:
            logger.warning("Skipping %s: expected height 16 and width 1..16, got %s", bmp_path, img.shape)
            continue
        _, binary = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY)
        stem = bmp_path.stem
        icons[stem] = binary
        # Also register Japanese aliases if English filename is used
        stem_lower = stem.lower()
        if stem_lower in WEATHER_ICON_ALIASES:
            for alias in WEATHER_ICON_ALIASES[stem_lower]:
                icons[alias] = binary
        logger.info("Loaded external weather icon: %s", bmp_path.name)
    return icons


def _load_all_external_icons() -> dict[str, np.ndarray]:
    """Load icons from all candidate directories, later directories overriding earlier."""
    merged: dict[str, np.ndarray] = {}
    for d in ICON_DIRS:
        merged.update(_load_external_bmp_icons(d))
    return merged


# BMP files placed in dashboard/icons/ override the hardcoded icons
EXTERNAL_WEATHER_ICONS = _load_all_external_icons()


def available_weather_icons() -> dict[str, np.ndarray]:
    """Return the merged weather icon table (external BMPs override hardcoded)."""
    merged = dict(HARDCODED_WEATHER_ICONS)
    merged.update(EXTERNAL_WEATHER_ICONS)
    return merged


def icon_for_weather(weather_text: str):
    """Return a 16x16 icon matching the given weather text, or None."""
    if not weather_text:
        return None
    table = available_weather_icons()
    if weather_text in table:
        return table[weather_text]
    for keyword, icon in table.items():
        if weather_text.startswith(keyword):
            return icon
    return None


def icon_for_train_status(label: str):
    """Return a 16x16 icon matching the given train status label, or None."""
    if not label:
        return None
    if label in HARDCODED_TRAIN_ICONS:
        return HARDCODED_TRAIN_ICONS[label]
    for keyword, icon in HARDCODED_TRAIN_ICONS.items():
        if keyword != "平常通り" and keyword in label:
            return icon
    return None

"""Text builders for Dashboard Mode.

These functions compose the human-readable strings shown on the LED matrix.
The actual scrolling is driven by ``scroll_engine.ScrollEngine``; this module
only knows how to assemble the text for a given state snapshot.

If ``available_icons`` contains an icon for the current weather text, the
renderer substitutes a private-use placeholder that
:mod:`scroll_engine` then renders as the 16x16 bitmap. Otherwise the actual
weather character is emitted so the dashboard never has gaps for missing
glyphs.
"""

from __future__ import annotations

from typing import Mapping, Optional

import numpy as np

from .state import DashboardState, WeatherInfo


LOCATION_LABEL = "目黒"
WEATHER_PLACEHOLDER = "\ue000"  # PUA: replaced by 16x16 weather icon if available

# Separator between weather block and train block.
BLOCK_SEPARATOR = "          "  # 10 ASCII spaces (~80 px gap)

# Separator between different city blocks.
CITY_SEPARATOR = "      "  # 6 ASCII spaces (~48 px gap)

# Separator between train line items.
TRAIN_ITEM_SEPARATOR = "  "  # 2 ASCII spaces (~16 px gap)


def _weather_segment(today_weather: str, available_icons: Mapping[str, np.ndarray]) -> str:
    """Return the weather-character segment with normalized half-width separators."""
    return (
        today_weather
        .replace("のち", "->")
        .replace("時々", "/")
        .replace("ときどき", "/")
    )


def _format_city_weather(
    city_name: str,
    w: WeatherInfo,
    available_icons: Mapping[str, np.ndarray],
) -> str:
    """Format single city weather into string."""
    parts: list[str] = [city_name]
    if w.error:
        parts.append(f"天気取得失敗({w.error})")
    elif w.today_weather:
        parts.append(_weather_segment(w.today_weather, available_icons))
    if w.today_high and w.today_low:
        high = w.today_high.removesuffix("度").removesuffix("℃")
        low = w.today_low.removesuffix("度").removesuffix("℃")
        parts.append(f"{high}/{low}℃")
    elif w.today_high:
        high = w.today_high.removesuffix("度").removesuffix("℃")
        parts.append(f"{high}℃")
    if w.warnings:
        joined = " ".join(w.warnings)
        if any("特別警報" in x for x in w.warnings):
            tag = "！特別警報！"
        elif any("警報" in x for x in w.warnings):
            tag = "！警報！"
        else:
            tag = "！注意報！"
        parts.append(f"{tag}{joined}{tag}")
    return " ".join(parts)


def build_weather_text(
    state: DashboardState,
    available_icons: Optional[Mapping[str, np.ndarray]] = None,
) -> str:
    """Compose the weather portion of the dashboard scroll text for all cities."""
    available_icons = available_icons or {}
    cities = state.get_cities_weather()

    # Ordered list: 目黒 -> 府中 -> 町田 -> 戸田 -> 横浜 -> 君津
    CITY_ORDER = [
        ("東京都目黒区", "目黒"),
        ("東京都府中市", "府中"),
        ("町田市", "町田"),
        ("埼玉県戸田市", "戸田"),
        ("神奈川県横浜市", "横浜"),
        ("千葉県君津市", "君津"),
    ]

    if cities:
        city_blocks: list[str] = []
        for key, display_name in CITY_ORDER:
            info = cities.get(key)
            if info is None:
                # Also support aliases if present
                if key == "東京都目黒区":
                    info = cities.get("目黒") or cities.get("目黒区")
            if info is None:
                continue

            city_blocks.append(_format_city_weather(display_name, info, available_icons))

        if city_blocks:
            return CITY_SEPARATOR.join(city_blocks)

    # Fallback to single weather record
    w = state.get_weather()
    return _format_city_weather(LOCATION_LABEL, w, available_icons)


def _train_status_label(status: str, error: Optional[str]) -> str:
    if error:
        return "取得失敗"
    if status == "平常運転":
        return "平常通り"
    return status


def _is_abnormal(status: str, error: Optional[str]) -> bool:
    """Check if train line status indicates delay, suspension, or error."""
    if error:
        return True
    if not status or status in ("平常運転", "通常運転"):
        return False
    return True


def build_train_text(state: DashboardState) -> str:
    """Compose the train status block shown alongside weather in the main scroll.

    If all lines are running normally without error, returns '運行情報：平常運転'.
    When delays or abnormalities occur, displays only the abnormal lines with
    expanded detail descriptions.
    """
    trains = state.get_trains()
    items: list[str] = []
    from .trains import DISPLAY_ORDER

    for line in DISPLAY_ORDER:
        ts = trains.get(line)
        if ts is None:
            continue
        if not _is_abnormal(ts.status, ts.error):
            continue

        label = _train_status_label(ts.status, ts.error)
        if ts.detail and not ts.error:
            short = _short_detail(ts.detail)
            items.append(f"{line} {label}({short})")
        else:
            items.append(f"{line} {label}")

    if not items:
        return "運行情報：平常運転" if trains else ""

    return "運行情報 " + TRAIN_ITEM_SEPARATOR.join(items)


def build_dashboard_text(
    state: DashboardState,
    available_icons: Optional[Mapping[str, np.ndarray]] = None,
) -> str:
    """Compose full dashboard scroll text: weather and (if any abnormal) train status."""
    weather_text = build_weather_text(state, available_icons)
    train_text = build_train_text(state)
    if not train_text:
        return weather_text
    return f"{weather_text}{BLOCK_SEPARATOR}{train_text}"


def weather_alert_tokens() -> list[str]:
    """Substrings whose columns should be flagged for inverted-flash."""
    return ["！注意報！", "！警報！", "！特別警報！"]


def _short_detail(detail: str, max_len: int = 256) -> str:
    """Format and truncate delay detail text (increased limit: 256 chars)."""
    detail = detail.replace("\u3000", " ").strip()
    return detail if len(detail) <= max_len else detail[: max_len - 1] + "…"

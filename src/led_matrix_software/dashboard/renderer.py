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

from .state import DashboardState


LOCATION_LABEL = "目黒区駒場"
WEATHER_PLACEHOLDER = "\ue000"  # PUA: replaced by 16x16 weather icon if available

# Separator between weather block and train block.
BLOCK_SEPARATOR = "          "  # 10 ASCII spaces (~80 px gap)

# Separator between train line items.
TRAIN_ITEM_SEPARATOR = "  "  # 2 ASCII spaces (~16 px gap)


def _weather_segment(today_weather: str, available_icons: Mapping[str, np.ndarray]) -> str:
    """Return the weather-character segment, using icon placeholder if possible."""
    if today_weather in available_icons:
        return f"本日 {WEATHER_PLACEHOLDER}"
    return f"本日 {today_weather}"


def build_weather_text(
    state: DashboardState,
    available_icons: Optional[Mapping[str, np.ndarray]] = None,
) -> str:
    """Compose the weather portion of the dashboard scroll text."""
    available_icons = available_icons or {}
    w = state.get_weather()
    parts: list[str] = [LOCATION_LABEL]
    if w.error:
        parts.append(f"天気取得失敗({w.error})")
    elif w.today_weather:
        parts.append(_weather_segment(w.today_weather, available_icons))
    if w.today_high and w.today_low:
        high = w.today_high.removesuffix("度")
        low = w.today_low.removesuffix("度")
        parts.append(f"気温{high}/{low}度")
    elif w.today_high:
        parts.append(f"最高{w.today_high}")
    if w.humidity:
        parts.append(f"湿度{w.humidity}")
    if w.warnings:
        joined = " ".join(w.warnings)
        parts.append(f"！注意報！{joined}！注意報！")
    return " ".join(parts)


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

    If all lines are running normally (or unretrieved without error), returns
    an empty string so normal status is not displayed. When delays or abnormalities
    occur, displays only the abnormal lines with expanded detail descriptions.
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
        return ""

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
    return ["！注意報！", "！警報！"]


def _short_detail(detail: str, max_len: int = 256) -> str:
    """Format and truncate delay detail text (increased limit: 256 chars)."""
    detail = detail.replace("\u3000", " ").strip()
    return detail if len(detail) <= max_len else detail[: max_len - 1] + "…"

"""Weather scraper for Dashboard Mode.

Fetches the Meguro-ku (Tokyo) forecast from tenki.jp and packages it as a
WeatherInfo. The Komaba area sits within Meguro-ku, so the area forecast is
the closest authoritative source.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .state import WeatherInfo, now_ts

logger = logging.getLogger(__name__)

MEGURO_FORECAST_URL = "https://tenki.jp/forecast/3/16/4410/13110/"
MEGURO_HOURLY_URL = "https://tenki.jp/forecast/3/16/4410/13110/3hours.html"
WARNING_LIST_URL = "https://tenki.jp/bousai/warn/"

HTTP_TIMEOUT = 10
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _http_get(url: str) -> Optional[str]:
    """Fetch URL with a desktop User-Agent; return text or None on failure."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("tenki.jp fetch %s -> HTTP %s", url, resp.status_code)
            return None
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except requests.RequestException as exc:
        logger.warning("tenki.jp fetch %s failed: %s", url, exc)
        return None


def _parse_temperature_value(s: str) -> str:
    """Extract numeric value from a tenki.jp temperature cell.

    Returns the value suffixed with the kanji 度 (U+5EA6) instead of the
    Celsius symbol ℃ (U+2103). Shinonome's zenkaku.bdf does not include the
    ℃ glyph even though the TSV maps it, so the symbol disappears during
    rendering and the surrounding text appears garbled on hardware.
    """
    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    return f"{m.group(1)}度" if m else s.strip()


def _parse_today_block(soup: BeautifulSoup) -> dict[str, str]:
    """Pull today's weather text, high/low temperature from the main forecast page."""
    today = soup.select_one("section.today-weather, .today-weather")
    if today is None:
        return {}

    weather_text = ""
    telop = today.select_one(".weather-telop")
    if telop is not None:
        weather_text = telop.get_text(strip=True)

    high, low = "", ""
    for span in today.select(".high-temp, .low-temp"):
        cls = " ".join(span.get("class", []))
        txt = span.get_text(strip=True)
        if not txt or txt in {"最高", "最低", "[0]", "[+1]", "[-1]"}:
            continue
        if "high" in cls:
            high = txt
        elif "low" in cls:
            low = txt

    return {
        "today_weather": weather_text,
        "today_high": _parse_temperature_value(high) if high else "",
        "today_low": _parse_temperature_value(low) if low else "",
    }


def _parse_current_humidity(soup: BeautifulSoup) -> str:
    """Pick the most recent numeric humidity entry from the 3-hour forecast table."""
    for tr in soup.select("tr"):
        th = tr.find("th")
        if th is None or "湿度" not in th.get_text():
            continue
        cells = [c.get_text(strip=True) for c in tr.find_all("td")]
        nums = [c for c in cells if re.fullmatch(r"-?\d+(?:\.\d+)?", c)]
        if nums:
            return f"{nums[-1]}%"
    return ""


def _parse_warnings(soup: BeautifulSoup) -> list[str]:
    """Return active 注意報 / 警報 names covering Tokyo from the warning summary."""
    rows = soup.select("table tr")
    active: list[str] = []
    for tr in rows:
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if not cells:
            continue
        if cells[0] not in {"警報", "注意報"}:
            continue
        if "東京" not in cells:
            continue
        warning_type = cells[1] if len(cells) > 1 else ""
        if warning_type:
            label = "警報" if cells[0] == "警報" else "注意報"
            active.append(f"{warning_type}{label}")
    return active


def fetch_weather() -> WeatherInfo:
    """Fetch weather + warnings for Meguro-ku and return a WeatherInfo snapshot."""
    main_html = _http_get(MEGURO_FORECAST_URL)
    if main_html is None:
        return WeatherInfo(error="tenki.jp main fetch failed", fetched_at=now_ts())

    soup = BeautifulSoup(main_html, "html.parser")
    info = _parse_today_block(soup)
    if not info:
        return WeatherInfo(error="tenki.jp parse failed", fetched_at=now_ts())

    hourly_html = _http_get(MEGURO_HOURLY_URL)
    if hourly_html is not None:
        info["humidity"] = _parse_current_humidity(BeautifulSoup(hourly_html, "html.parser"))
    else:
        info["humidity"] = ""

    warnings_html = _http_get(WARNING_LIST_URL)
    if warnings_html is not None:
        info["warnings"] = _parse_warnings(BeautifulSoup(warnings_html, "html.parser"))
    else:
        info["warnings"] = []

    return WeatherInfo(
        today_weather=info.get("today_weather", ""),
        today_high=info.get("today_high", ""),
        today_low=info.get("today_low", ""),
        humidity=info.get("humidity", ""),
        warnings=info.get("warnings", []),
        fetched_at=now_ts(),
    )

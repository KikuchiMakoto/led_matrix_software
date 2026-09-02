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
TOKYO_WARNING_URL = "https://tenki.jp/bousai/warn/3/16/"
WARNING_LIST_URL = "https://tenki.jp/bousai/warn/"

HTTP_TIMEOUT = 10
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _http_get(url: str) -> Optional[str]:
    """Fetch URL with desktop User-Agent; enforce UTF-8 as tenki.jp is UTF-8."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("tenki.jp fetch %s -> HTTP %s", url, resp.status_code)
            return None
        # tenki.jp pages are always UTF-8; apparent_encoding can guess cp932/euc-jp
        resp.encoding = "utf-8"
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
    if not weather_text:
        img = today.select_one("img[alt]")
        if img and img.get("alt"):
            weather_text = img["alt"].strip()

    high, low = "", ""

    # Specifically target temperature cells (.temp) and avoid diff cells (.tempdiff)
    high_temp_elem = today.select_one("dd.high-temp.temp, .high-temp.temp, .high-temp .temp")
    if high_temp_elem is not None:
        high = high_temp_elem.get_text(strip=True)

    low_temp_elem = today.select_one("dd.low-temp.temp, .low-temp.temp, .low-temp .temp")
    if low_temp_elem is not None:
        low = low_temp_elem.get_text(strip=True)

    # Fallback if specific classes differ: scan .high-temp and .low-temp while strictly excluding .tempdiff
    if not high or not low:
        for span in today.select(".high-temp, .low-temp"):
            cls = span.get("class", [])
            if "tempdiff" in cls or "sumarry" in cls:
                continue
            txt = span.get_text(strip=True)
            if not txt or re.match(r"^\[[+-]?\d+\]$", txt) or txt in {"最高", "最低"}:
                continue
            cls_str = " ".join(cls)
            if "high" in cls_str and not high:
                high = txt
            elif "low" in cls_str and not low:
                low = txt

    return {
        "today_weather": weather_text,
        "today_high": _parse_temperature_value(high) if high else "",
        "today_low": _parse_temperature_value(low) if low else "",
    }


def _parse_current_humidity(soup: BeautifulSoup) -> str:
    """Pick the humidity entry closest to the current time from the 3-hour forecast table."""
    import datetime

    current_hour = datetime.datetime.now().hour

    # Try 3-hour table for today
    table = soup.select_one("#forecast-point-3h-today, table.forecast-point-3h")
    if table is not None:
        hour_tds = [td.get_text(strip=True) for td in table.select("tr.hour td")]
        humid_tds = [td.get_text(strip=True) for td in table.select("tr.humidity td")]

        if hour_tds and len(hour_tds) == len(humid_tds):
            parsed_entries: list[tuple[int, str]] = []
            for h_str, hum in zip(hour_tds, humid_tds):
                m_h = re.search(r"\d+", h_str)
                m_hum = re.search(r"\d+", hum)
                if m_h and m_hum:
                    parsed_entries.append((int(m_h.group(0)), m_hum.group(0)))

            if parsed_entries:
                # Find entry closest to current hour (e.g. 14 -> 15)
                best_entry = min(parsed_entries, key=lambda item: abs(item[0] - current_hour))
                return f"{best_entry[1]}%"

    # Fallback: find any humidity row and pick the closest numeric value
    for tr in soup.select("tr"):
        th = tr.find("th")
        if th is None or "湿度" not in th.get_text():
            continue
        cells = [c.get_text(strip=True) for c in tr.find_all("td")]
        nums = [re.search(r"\d+", c).group(0) for c in cells if re.search(r"\d+", c)]
        if nums:
            # Pick first available or closest
            idx = min(max(0, current_hour // 3), len(nums) - 1)
            return f"{nums[idx]}%"
    return ""


def _parse_warnings(soup_tokyo: Optional[BeautifulSoup], soup_all: Optional[BeautifulSoup]) -> list[str]:
    """Return active 注意報 / 警報 names covering Meguro-ku / Tokyo from tenki.jp warning tables."""
    active: list[str] = []

    # First check Tokyo warning page which lists municipal areas including Meguro-ku
    if soup_tokyo is not None:
        for tr in soup_tokyo.select("table tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
            if any("目黒" in c for c in cells):
                for cell in cells:
                    if cell in {"目黒区", "発表なし", "-"}:
                        continue
                    # Any warnings listed (e.g., 強風注意報, 大雨警報, etc.)
                    for w in re.findall(r"[\u4e00-\u9fa5]+(?:警報|注意報)", cell):
                        if w not in active:
                            active.append(w)
                if active:
                    return active

    # Fallback to nationwide summary table
    if soup_all is not None:
        for tr in soup_all.select("table tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
            if len(cells) < 2 or cells[0] not in {"警報", "注意報"}:
                continue
            if "東京" not in cells:
                continue
            warning_type = cells[1]
            if warning_type:
                label = "警報" if cells[0] == "警報" else "注意報"
                name = f"{warning_type}{label}"
                if name not in active:
                    active.append(name)

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

    tokyo_warn_html = _http_get(TOKYO_WARNING_URL)
    all_warn_html = _http_get(WARNING_LIST_URL) if tokyo_warn_html is None else None
    soup_tokyo = BeautifulSoup(tokyo_warn_html, "html.parser") if tokyo_warn_html else None
    soup_all = BeautifulSoup(all_warn_html, "html.parser") if all_warn_html else None
    info["warnings"] = _parse_warnings(soup_tokyo, soup_all)

    return WeatherInfo(
        today_weather=info.get("today_weather", ""),
        today_high=info.get("today_high", ""),
        today_low=info.get("today_low", ""),
        humidity=info.get("humidity", ""),
        warnings=info.get("warnings", []),
        fetched_at=now_ts(),
    )

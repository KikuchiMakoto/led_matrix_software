"""Train delay scraper for Dashboard Mode.

Scrapes Yahoo! Transit's per-line status pages for the four Komaba-area
target lines (Keio Main, Keio Inokashira, Chiyoda, Odakyu Odawara) and returns
a fresh mapping of line -> TrainStatus.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .state import TrainStatus, now_ts

logger = logging.getLogger(__name__)

LINE_NAMES = {
    "京王本線": 102,
    "京王井の頭線": 108,
    "小田急小田原線": 109,
    "東京メトロ千代田線": 136,
}

LINE_ALIASES = {
    "京王本線": "京王本線",
    "京王線": "京王本線",
    "京王井の頭線": "京王井の頭線",
    "井の頭線": "京王井の頭線",
    "小田急小田原線": "小田急小田原線",
    "小田急線": "小田急小田原線",
    "小田急": "小田急小田原線",
    "東京メトロ千代田線": "東京メトロ千代田線",
    "千代田線": "東京メトロ千代田線",
}

DISPLAY_ORDER = ["京王本線", "京王井の頭線", "東京メトロ千代田線", "小田急小田原線"]

HTTP_TIMEOUT = 10
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _detail_url(rail_code: int) -> str:
    return f"https://transit.yahoo.co.jp/traininfo/detail/{rail_code}/0/"


def _http_get(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("Yahoo Transit fetch %s -> HTTP %s", url, resp.status_code)
            return None
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except requests.RequestException as exc:
        logger.warning("Yahoo Transit fetch %s failed: %s", url, exc)
        return None


def _parse_status(html: str) -> tuple[str, str]:
    """Return (status_label, detail_text) parsed from a Yahoo Transit detail page."""
    soup = BeautifulSoup(html, "html.parser")
    dt = soup.find("dt")
    if dt is None:
        return ("不明", "")
    status = dt.get_text(strip=True)
    dd = dt.find_next_sibling("dd")
    detail = dd.get_text(" ", strip=True) if dd is not None else ""
    return (status, detail)


def _fetch_one(display_name: str, rail_code: int) -> TrainStatus:
    html = _http_get(_detail_url(rail_code))
    if html is None:
        return TrainStatus(line=display_name, error="fetch failed", fetched_at=now_ts())
    status, detail = _parse_status(html)
    return TrainStatus(
        line=display_name,
        status=status,
        detail=detail,
        fetched_at=now_ts(),
    )


def fetch_all_trains() -> dict[str, TrainStatus]:
    """Fetch all four target lines in parallel."""
    results: dict[str, TrainStatus] = {}
    with ThreadPoolExecutor(max_workers=len(LINE_NAMES)) as pool:
        futures = {pool.submit(_fetch_one, name, code): name for name, code in LINE_NAMES.items()}
        for fut, name in futures.items():
            try:
                results[name] = fut.result()
            except Exception as exc:
                logger.warning("Train fetch %s raised: %s", name, exc)
                results[name] = TrainStatus(line=name, error=str(exc), fetched_at=now_ts())
    return results

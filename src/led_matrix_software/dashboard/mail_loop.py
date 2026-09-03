"""Asynchronous MailLoop driving the LED matrix in Dashboard Mode.

Architecture (two-stage buffer):

* Fetcher thread periodically scrapes weather + trains and updates ``state``.
  The renderable text is produced by the display loop on demand so the
  matrix never goes blank.
* Display thread owns a :class:`ScrollEngine` whose 128x16 buffer is fed by
  a column FIFO. Each tick shifts the buffer one column left and pulls the
  next column from the FIFO. When the FIFO is empty, the display loop
  re-enqueues the latest weather + train text so the scroll loops
  continuously with fresh data.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from ..matrix import make_matrix_buffer
from .renderer import build_dashboard_text, weather_alert_tokens
from .scroll_engine import Column, ScrollEngine
from .state import DashboardState, MessageQueue
from .trains import fetch_all_trains
from .weather import fetch_weather
from .weather_icons import EXTERNAL_WEATHER_ICONS

logger = logging.getLogger(__name__)


class DashboardMailLoop:
    """Coordinator that wires fetcher and display threads."""

    def __init__(
        self,
        device,
        font,
        state: DashboardState,
        *,
        weather_interval: float = 600.0,
        train_interval: float = 60.0,
        scroll_speed: float = 0.01,
        alert_scroll_speed: float = 0.04,
        on_update: Optional[Callable[[DashboardState], None]] = None,
    ) -> None:
        self.device = device
        self.font = font
        self.state = state
        self.weather_interval = float(weather_interval)
        self.train_interval = float(train_interval)
        self.scroll_speed = float(scroll_speed)
        self.alert_scroll_speed = float(alert_scroll_speed)
        self.on_update = on_update
        self._stop_event = threading.Event()
        self._fetcher_thread: Optional[threading.Thread] = None
        self._engine: Optional[ScrollEngine] = None
        self._queue: MessageQueue = MessageQueue()
        # Loaded once at startup; subsequent BMP drops require a restart.
        # Only external BMPs trigger icon rendering; hardcoded fallback icons
        # are intentionally ignored by default (per user preference).
        self._available_icons = dict(EXTERNAL_WEATHER_ICONS)

    def start(self) -> None:
        """Start fetcher thread and run the MailLoop until interrupted."""
        self._engine = ScrollEngine(self.font)
        self._fetcher_thread = threading.Thread(
            target=self._fetch_loop, daemon=True, name="dashboard-fetcher"
        )
        self._fetcher_thread.start()
        try:
            self._display_loop()
        except KeyboardInterrupt:
            logger.info("Dashboard MailLoop stopped by user")
        finally:
            self.stop()

    def stop(self) -> None:
        self._stop_event.set()
        if self._fetcher_thread is not None:
            self._fetcher_thread.join(timeout=2.0)

    def _fetch_loop(self) -> None:
        # Initial concurrent fetch so trains aren't shown as 未取得 during the
        # first weather-only window.
        with ThreadPoolExecutor(max_workers=2) as pool:
            weather_fut = pool.submit(self._safe_fetch_weather)
            trains_fut = pool.submit(self._safe_fetch_trains)
            weather_fut.result(timeout=20)
            trains_fut.result(timeout=20)

        if self.on_update is not None:
            try:
                self.on_update(self.state)
            except Exception as exc:
                logger.warning("on_update callback raised: %s", exc)

        while not self._stop_event.is_set():
            if self._stop_event.wait(self.train_interval):
                break
            self._safe_fetch_trains()

            remaining = max(self.weather_interval - self.train_interval, 1.0)
            if self._stop_event.wait(remaining):
                break
            self._safe_fetch_weather()

            if self.on_update is not None:
                try:
                    self.on_update(self.state)
                except Exception as exc:
                    logger.warning("on_update callback raised: %s", exc)

    def _safe_fetch_weather(self) -> None:
        try:
            from .weather import fetch_all_cities_weather

            cities = fetch_all_cities_weather()
            self.state.update_cities_weather(cities)
            logger.info("Fetched weather for cities: %s", ", ".join(cities.keys()))
        except Exception as exc:
            logger.warning("Weather fetch raised: %s", exc)

    def _safe_fetch_trains(self) -> None:
        try:
            trains = fetch_all_trains()
            self.state.update_trains(trains)
            logger.info(
                "Trains fetched: %s",
                ", ".join(f"{name}={ts.status}" for name, ts in trains.items()),
            )
        except Exception as exc:
            logger.warning("Train fetch raised: %s", exc)

    def _display_loop(self) -> None:
        assert self._engine is not None
        from ..timing import PreciseTicker

        engine = self._engine
        engine.enqueue_padding(screen_widths=1)
        ticker = PreciseTicker(self.scroll_speed)

        while not self._stop_event.is_set():
            if engine.pending_count() == 0:
                self._refill_dashboard(engine)
            engine.step()
            matrix = make_matrix_buffer(engine.buffer)
            self.device.write(matrix)
            ticker.sleep_until_next(self._next_delay(engine))

    def _refill_dashboard(self, engine: ScrollEngine) -> None:
        weather = self.state.get_weather()
        text = build_dashboard_text(self.state, self._available_icons)
        if not text:
            engine.enqueue_padding(screen_widths=1)
            return
        tokens = weather_alert_tokens() if weather.has_warnings else None
        # Pass external BMP icons as character overrides so that any matching
        # weather characters (across all cities) render as 16x16 bitmaps.
        icon_overrides = self._available_icons if self._available_icons else None
        engine.enqueue_text(text, alert_tokens=tokens, icon_overrides=icon_overrides)

    def _next_delay(self, engine: ScrollEngine) -> float:
        """Use alert_scroll_speed when the next FIFO column is flagged."""
        if engine.pending_count() == 0:
            return self.scroll_speed
        next_col: Column = engine.peek_next()
        return self.alert_scroll_speed if next_col.is_alert else self.scroll_speed

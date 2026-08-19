"""Thread-safe shared state for Dashboard Mode.

The fetcher thread updates the state periodically; the renderer reads from
it. All mutations happen under a single lock so the renderer never sees a
half-updated record. The producer / consumer split is enforced via a small
:class:`MessageQueue` for the ScrollEngine FIFO producer side.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WeatherInfo:
    """Weather snapshot for Tokyo Meguro-ku (Komaba)."""

    today_weather: str = ""
    today_high: str = ""
    today_low: str = ""
    humidity: str = ""
    warnings: list[str] = field(default_factory=list)
    fetched_at: float = 0.0
    error: Optional[str] = None

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def is_fresh(self) -> bool:
        return self.fetched_at > 0.0 and self.error is None


@dataclass
class TrainStatus:
    """Train delay status for a single line."""

    line: str
    status: str = "平常"
    detail: str = ""
    fetched_at: float = 0.0
    error: Optional[str] = None

    @property
    def is_normal(self) -> bool:
        return self.status == "平常"

    @property
    def is_fresh(self) -> bool:
        return self.fetched_at > 0.0


@dataclass
class DisplayMessage:
    """A pending message ready to be pushed into the scroll engine FIFO."""

    kind: str  # "weather" | "trains" | "padding"
    text: str
    is_priority: bool = False
    alert_tokens: list[str] = field(default_factory=list)


class MessageQueue:
    """Bounded FIFO between fetcher (producer) and ScrollEngine (consumer)."""

    def __init__(self, max_size: int = 8) -> None:
        self._queue: queue.Queue[DisplayMessage] = queue.Queue(maxsize=max_size)
        self._latest_train_signature: Optional[tuple] = None
        self._lock = threading.Lock()

    def submit(self, msg: DisplayMessage) -> None:
        """Enqueue a message.

        Priority messages drain the existing queue first so that fresh
        disruption info reaches the display as soon as possible.
        Non-priority submissions silently drop when the queue is full so the
        producer never blocks.
        """
        with self._lock:
            if msg.is_priority:
                self._drain_locked()
            try:
                self._queue.put_nowait(msg)
            except queue.Full:
                if not msg.is_priority:
                    return
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(msg)
                except (queue.Empty, queue.Full):
                    pass

    def get(self, timeout: float = 1.0) -> Optional[DisplayMessage]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_nowait(self) -> Optional[DisplayMessage]:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def has_pending(self) -> bool:
        return not self._queue.empty()

    def note_train_signature(self, signature: tuple) -> bool:
        """Return True iff the signature is new (and a disruption is present)."""
        with self._lock:
            if signature == self._latest_train_signature:
                return False
            self._latest_train_signature = signature
            return any(status != "平常" for _, status, _detail in signature)

    def _drain_locked(self) -> None:
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass


class DashboardState:
    """Shared weather + train snapshot with mutex protection."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._weather: WeatherInfo = WeatherInfo()
        self._trains: dict[str, TrainStatus] = {}

    def update_weather(self, weather: WeatherInfo) -> None:
        with self._lock:
            self._weather = weather

    def update_trains(self, trains: dict[str, TrainStatus]) -> None:
        with self._lock:
            self._trains = dict(trains)

    def get_weather(self) -> WeatherInfo:
        with self._lock:
            return self._weather

    def get_trains(self) -> dict[str, TrainStatus]:
        with self._lock:
            return dict(self._trains)


def now_ts() -> float:
    return time.time()

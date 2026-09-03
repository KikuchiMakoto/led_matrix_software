"""High-precision timing utilities for real-time LED matrix rendering.

On Linux, standard Python ``time.sleep()`` relies on POSIX nanosleep with
default slack, which often introduces jitter (1-3ms) and frame drift.
This module leverages Linux's ``clock_nanosleep`` with ``TIMER_ABSTIME``
(CLOCK_MONOTONIC) via libc ctypes, achieving sub-millisecond precision
and absolute deadline tracking without accumulative drift.

On Windows/macOS, it transparently falls back to a drift-compensated
``time.perf_counter()`` loop.
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from typing import Optional

_HAS_CLOCK_NANOSLEEP = False
_libc = None

if sys.platform.startswith("linux"):
    try:
        class Timespec(ctypes.Structure):
            _fields_ = [
                ("tv_sec", ctypes.c_long),
                ("tv_nsec", ctypes.c_long),
            ]

        _libc = ctypes.CDLL("libc.so.6", use_errno=True)
        _libc.clock_nanosleep.argtypes = [
            ctypes.c_int,  # clockid_t
            ctypes.c_int,  # flags
            ctypes.POINTER(Timespec),  # const struct timespec *request
            ctypes.POINTER(Timespec),  # struct timespec *remain
        ]
        _libc.clock_nanosleep.restype = ctypes.c_int

        CLOCK_MONOTONIC = 1
        TIMER_ABSTIME = 1
        _HAS_CLOCK_NANOSLEEP = True
    except Exception:
        _HAS_CLOCK_NANOSLEEP = False


class PreciseTicker:
    """Drift-free periodic timer for rendering loops."""

    def __init__(self, interval: float) -> None:
        self.interval = float(interval)
        self._next_deadline: float = time.perf_counter()

    def reset(self, interval: Optional[float] = None) -> None:
        if interval is not None:
            self.interval = float(interval)
        self._next_deadline = time.perf_counter()

    def sleep_until_next(self, interval: Optional[float] = None) -> None:
        """Sleep until the next periodic deadline, updating target interval if given."""
        if interval is not None:
            self.interval = float(interval)

        self._next_deadline += self.interval
        now = time.perf_counter()

        # If we fell behind schedule by more than 2 frames, catch up
        if now > self._next_deadline + self.interval * 2:
            self._next_deadline = now + self.interval
            return

        remaining = self._next_deadline - now
        if remaining <= 0:
            return

        if _HAS_CLOCK_NANOSLEEP and _libc is not None:
            # Absolute nanosleep on Linux using CLOCK_MONOTONIC
            # Note: time.monotonic() / time.perf_counter() on Linux is CLOCK_MONOTONIC
            sec = int(self._next_deadline)
            nsec = int((self._next_deadline - sec) * 1_000_000_000)
            req = Timespec(tv_sec=sec, tv_nsec=nsec)
            _libc.clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, ctypes.byref(req), None)
        else:
            # Fallback for Windows/macOS with spin-wait fine tuning for last ~0.5ms
            if remaining > 0.002:
                time.sleep(remaining - 0.001)
            while time.perf_counter() < self._next_deadline:
                pass


def optimize_display_thread_priority() -> str:
    """Optimize current thread priority for real-time display on Linux.

    Attempts SCHED_FIFO first (if permitted), then falls back to the most
    favorable nice level allowed for the current user. Safe on non-Linux platforms.

    Returns:
        Description string of the applied priority setting.
    """
    if not sys.platform.startswith("linux"):
        return "non-linux (default priority)"

    # 1. Try SCHED_FIFO real-time scheduler
    try:
        if hasattr(os, "sched_setscheduler") and hasattr(os, "SCHED_FIFO"):
            param = os.sched_param(50)
            os.sched_setscheduler(0, os.SCHED_FIFO, param)
            return "SCHED_FIFO(priority=50)"
    except (PermissionError, OSError):
        pass

    # 2. Try best possible nice level (-20 down to -1) allowed without sudo
    current_nice = os.nice(0)
    for target in range(-20, current_nice):
        try:
            delta = target - current_nice
            new_nice = os.nice(delta)
            return f"nice={new_nice}"
        except (PermissionError, OSError):
            continue

    return f"nice={current_nice} (default)"


def deprioritize_background_thread() -> str:
    """Set the current thread to the lowest priority (idle / nice=19) on Linux.

    Safe for unprivileged users (sudo is never required to lower priority).
    Ensures background network/scraping workers never steal CPU from rendering.

    Returns:
        Description string of the applied priority setting.
    """
    if not sys.platform.startswith("linux"):
        return "non-linux"

    try:
        current_nice = os.nice(0)
        target = 19
        if current_nice < target:
            new_nice = os.nice(target - current_nice)
            return f"nice={new_nice}"
    except (PermissionError, OSError):
        pass

    return "nice=unchanged"


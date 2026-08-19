"""Dashboard Mode for LED Matrix Display.

Provides an asynchronous MailLoop that scrolls weather forecasts and train
delay information for Tokyo Meguro-ku (Komaba) on a 16-pixel LED matrix.

Components:
    state          : Thread-safe shared state container
    weather        : tenki.jp weather scraper (Meguro-ku)
    trains         : Yahoo! Transit train delay scraper (4 lines)
    renderer       : Text builder
    weather_icons  : Hand-drawn 16x16 bitmaps (used via ScrollEngine.icon_overrides)
    scroll_engine  : Two-stage buffer driver with optional icon injection
    mail_loop      : Asynchronous fetcher and display coordinator
"""

from .state import DashboardState, WeatherInfo, TrainStatus
from .weather import fetch_weather
from .trains import fetch_all_trains, LINE_NAMES
from .mail_loop import DashboardMailLoop

__all__ = [
    "DashboardState",
    "WeatherInfo",
    "TrainStatus",
    "fetch_weather",
    "fetch_all_trains",
    "LINE_NAMES",
    "DashboardMailLoop",
]

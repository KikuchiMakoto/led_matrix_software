"""System tray (task tray) support for background operation.

Used by ``--bg``: the display work runs in a worker thread while a tray icon
stays resident. The tray icon itself is a live thumbnail of the actual 128x16
matrix content (split into two 64px bands), and "Preview" opens a larger live
window. "Quit" sets the stop event so the worker shuts down cleanly.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

import numpy as np

from .devices import matrix_to_pixels

LED_COLOR = (255, 176, 0)
LED_DIM = (40, 30, 0)

FrameSource = Callable[[], Optional[np.ndarray]]


def _idle_icon_pixels() -> np.ndarray:
    """Fallback content shown before the first frame arrives."""
    pixels = np.zeros((16, 128), dtype=bool)
    pixels[7:9, ::4] = True
    return pixels


def _pixels_to_icon(pixels: np.ndarray, size: int = 64) -> "object":
    """Render the 128x16 content as a square tray icon (two stacked bands)."""
    from PIL import Image

    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    band_width = size
    band_height = 16
    gap = 2
    total = band_height * 2 + gap
    top = max((size - total) // 2, 0)

    for band in range(2):
        segment = pixels[:, band * 64 : (band + 1) * 64]
        # 64 source columns -> icon width (nearest neighbour).
        cols = np.clip((np.arange(band_width) * segment.shape[1]) // band_width, 0, 63)
        scaled = segment[:, cols]
        y0 = top + band * (band_height + gap)
        view = canvas[y0 : y0 + band_height, 0:band_width]
        view[scaled] = LED_COLOR
        view[~scaled] = LED_DIM

    return Image.fromarray(canvas, "RGB")


def _pixels_to_preview(pixels: np.ndarray, scale: int = 4) -> "object":
    """Render the 128x16 content as an enlarged LED-like preview image."""
    from PIL import Image

    rgb = np.zeros((pixels.shape[0], pixels.shape[1], 3), dtype=np.uint8)
    rgb[pixels] = LED_COLOR
    rgb[~pixels] = (25, 18, 0)
    big = np.kron(rgb, np.ones((scale, scale, 1), dtype=np.uint8))
    return Image.fromarray(big, "RGB")


def _current_pixels(frame_source: Optional[FrameSource]) -> np.ndarray:
    if frame_source is None:
        return _idle_icon_pixels()
    frame = frame_source()
    if frame is None:
        return _idle_icon_pixels()
    return matrix_to_pixels(frame)


def _open_preview(frame_source: FrameSource, stop_event: threading.Event, title: str) -> None:
    """Open a live preview window in its own thread (all Tk calls stay there)."""

    def run():
        try:
            import tkinter as tk
            from PIL import ImageTk
        except ImportError as e:  # pragma: no cover - tkinter/PIL missing
            print(f"Warning: preview window unavailable ({e}).")
            return

        root = tk.Tk()
        root.title(f"{title} - Preview")
        root.configure(bg="black")
        root.resizable(False, False)
        label = tk.Label(root, bd=0, bg="black")
        label.pack()

        def tick():
            if stop_event.is_set():
                root.destroy()
                return
            image = ImageTk.PhotoImage(_pixels_to_preview(_current_pixels(frame_source)))
            label.configure(image=image)
            label.image = image
            root.after(100, tick)

        tick()
        root.mainloop()

    threading.Thread(target=run, daemon=True, name="led-matrix-preview").start()


def run_in_tray(
    worker: Callable[[threading.Event], None],
    *,
    title: str = "LED Matrix",
    status: str = "",
    frame_source: Optional[FrameSource] = None,
    thumbnail_interval: float = 0.25,
) -> None:
    """Run ``worker(stop_event)`` in a thread while showing a tray icon.

    Args:
        worker: Callable receiving a stop event; runs in a background thread.
        title: Tray icon title.
        status: Extra text shown in the tooltip / menu header.
        frame_source: Optional callable returning the latest matrix buffer,
            used for the live thumbnail and preview window.
        thumbnail_interval: Seconds between tray thumbnail updates.
    """
    stop_event = threading.Event()

    try:
        import pystray
    except ImportError:
        print("Warning: pystray is not installed; running in the foreground instead.")
        worker(stop_event)
        return

    tooltip = f"{title} - {status}" if status else title
    icon = pystray.Icon("led_matrix", _pixels_to_icon(_current_pixels(frame_source)), tooltip)

    def on_quit(_icon, _item):
        stop_event.set()
        _icon.visible = False
        _icon.stop()

    def on_preview(_icon, _item):
        if frame_source is not None:
            _open_preview(frame_source, stop_event, title)

    menu_items = []
    if status:
        menu_items.append(pystray.MenuItem(status, None, enabled=False))
        menu_items.append(pystray.Menu.SEPARATOR)
    if frame_source is not None:
        menu_items.append(pystray.MenuItem("Preview", on_preview, default=True))
    menu_items.append(pystray.MenuItem("Quit", on_quit))
    icon.menu = pystray.Menu(*menu_items)

    def run_worker():
        try:
            worker(stop_event)
        finally:
            stop_event.set()
            try:
                icon.stop()
            except Exception:  # pragma: no cover - tray already gone
                pass

    def update_thumbnail():
        while not stop_event.wait(thumbnail_interval):
            try:
                icon.icon = _pixels_to_icon(_current_pixels(frame_source))
            except Exception:  # pragma: no cover - tray already gone
                break

    thread = threading.Thread(target=run_worker, daemon=True, name="led-matrix-worker")
    thread.start()
    if frame_source is not None:
        threading.Thread(target=update_thumbnail, daemon=True, name="led-matrix-thumb").start()

    try:
        icon.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:  # pragma: no cover - platform dependent
        print(f"Warning: tray icon unavailable ({e}); waiting in the foreground.")
        try:
            while thread.is_alive():
                thread.join(timeout=0.5)
        except KeyboardInterrupt:
            pass
    finally:
        stop_event.set()
        thread.join(timeout=5.0)

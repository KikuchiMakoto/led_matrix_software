"""Power management helpers.

While the LED matrix is being driven we must keep the machine awake, but the
screen is allowed to turn off / lock (the display is not the output device).

``wakepy``'s ``keep.running`` mode does exactly that: system sleep is inhibited
while screen lock / screen blanking stays enabled.
"""

from contextlib import contextmanager


@contextmanager
def prevent_sleep(*, verbose: bool = True):
    """Keep the system awake while allowing the screen to lock or turn off.

    Falls back to a no-op (with a warning) if wakepy is unavailable or the
    platform cannot be kept awake, so display never fails because of this.
    """
    try:
        from wakepy import keep
    except ImportError:
        if verbose:
            print("Warning: wakepy is not installed; system sleep is not inhibited.")
        yield False
        return

    try:
        with keep.running(on_fail="warn") as mode:
            if verbose:
                if mode.active:
                    print("Sleep inhibited (screen lock / screen off still allowed).")
                else:
                    print("Warning: failed to inhibit system sleep; continuing anyway.")
            yield bool(mode.active)
    except Exception as e:  # pragma: no cover - platform dependent
        if verbose:
            print(f"Warning: failed to inhibit system sleep ({e}); continuing anyway.")
        yield False

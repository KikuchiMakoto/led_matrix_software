"""Detached background launch support for ``--bg``.

``--bg`` re-launches this program as a detached, console-less child process and
returns immediately, so the terminal is freed and closing it does not kill the
display. The child stays resident in the task tray and is stopped from the
tray menu ("Quit"). Its stdout/stderr are redirected to a log file.
"""

from __future__ import annotations

import os
import subprocess
import sys

BG_CHILD_ENV = "LED_MATRIX_BG_CHILD"
DEFAULT_LOG_NAME = "led_matrix_bg.log"


def is_bg_child() -> bool:
    """True when the current process is the detached background child."""
    return os.environ.get(BG_CHILD_ENV) == "1"


def _script_to_module(argv0: str) -> str | None:
    """Map a script path like ``src/led_matrix_software/main.py`` to ``-m`` form."""
    if not argv0 or argv0.startswith("-"):
        return None
    path = os.path.abspath(argv0).replace(os.sep, "/")
    marker = "/src/led_matrix_software/"
    idx = path.find(marker)
    if idx == -1:
        return None
    rest = path[idx + len(marker) :]
    if rest.endswith(".py"):
        rest = rest[:-3]
    if rest.endswith("/__init__"):
        rest = rest[: -len("/__init__")]
    rest = rest.replace("/", ".")
    return f"src.led_matrix_software.{rest}" if rest else "src.led_matrix_software"


def _windowless_command() -> list[str]:
    """Build a command line that runs this program without a console window.

    Detects ``uv run`` invocations (which rewrite ``sys.executable``) and, on
    Windows, swaps ``python.exe`` for ``pythonw.exe`` so the detached child
    runs without a console. ``python -m pkg`` style invocations are preserved
    so relative imports keep working. Plain ``python main.py`` invocations are
    rewritten to ``python -m pkg.main`` so the detached child has the right
    package context too.
    """
    uv_exe = os.environ.get("UV")
    is_uv = bool(uv_exe) and os.path.exists(uv_exe)

    script = sys.argv[0]
    extra_args = sys.argv[1:]

    if is_uv:
        # ``uv run`` rewrites argv[0] so ``-m`` ends up inside ``script``.
        # Reconstruct: ``uv run python <script> <args...>``.
        return [uv_exe, "run", "python", script, *extra_args]

    executable = sys.executable
    if os.name == "nt":
        candidate = os.path.join(os.path.dirname(executable), "pythonw.exe")
        if os.path.exists(candidate):
            executable = candidate

    if script == "-m" or script == "-c":
        return [executable, script, *extra_args]

    module = _script_to_module(script)
    if module is not None:
        return [executable, "-m", module, *extra_args]
    return [executable, os.path.abspath(script), *extra_args]


def relaunch_detached(log_path: str = DEFAULT_LOG_NAME) -> tuple[int, str]:
    """Start a detached copy of this process; return ``(pid, log_path)``."""
    argv = _windowless_command()

    env = os.environ.copy()
    env[BG_CHILD_ENV] = "1"

    log_path = os.path.abspath(log_path)
    log = open(log_path, "ab", buffering=0)

    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": log,
        "stderr": subprocess.STDOUT,
        "env": env,
        "cwd": os.getcwd(),
        "close_fds": True,
    }
    if os.name == "nt":
        detached_process = 0x00000008
        create_new_process_group = 0x00000200
        create_no_window = 0x08000000
        kwargs["creationflags"] = detached_process | create_new_process_group | create_no_window
    else:
        kwargs["start_new_session"] = True

    try:
        process = subprocess.Popen(argv, **kwargs)
    finally:
        log.close()

    return process.pid, log_path

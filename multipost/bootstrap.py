"""First-run bootstrap for the frozen (.exe) build.

PySide6 + Playwright cannot bundle the Chromium browser binary itself, so on
first publish the exe downloads Chromium (~170 MB) into data/browsers next to
the exe. Source-mode runs use `playwright install chromium` from run.bat
instead and skip this entirely.
"""

from __future__ import annotations

import os
import subprocess
import sys

_done = False


def browsers_path() -> str | None:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
        return os.path.join(base, "data", "browsers")
    return None


def ensure_chromium() -> None:
    global _done
    if _done:
        return
    _done = True
    path = browsers_path()
    if path is None:
        return  # source mode: run.bat already installed the browser
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", path)
    if os.path.isdir(path) and os.listdir(path):
        return
    os.makedirs(path, exist_ok=True)
    try:
        from playwright._impl._driver import compute_driver_executable

        driver = compute_driver_executable()
        if isinstance(driver, (tuple, list)):
            cmd = list(driver) + ["install", "chromium"]
        else:
            cmd = [str(driver), "install", "chromium"]
        subprocess.run(cmd, check=False, timeout=1800)
    except Exception:
        # If the download fails, the publisher will surface Playwright's own
        # "browser not found" error with the manual fix - never hide it here.
        pass

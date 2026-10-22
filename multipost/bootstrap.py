"""Browser engine selection + first-run bootstrap.

Lightweight by default: on Windows the app drives the Microsoft Edge that
already ships with Windows 11 (Playwright `channel="msedge"`) - NO 170 MB
Chromium download, nothing extra installed. Chrome is the second choice.
The bundled Playwright Chromium is only downloaded when neither exists.

Force a choice with the env var MULTIPOST_BROWSER=edge|chrome|chromium.
"""

from __future__ import annotations

import os
import subprocess
import sys

_done = False

_EDGE_PATHS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
_CHROME_PATHS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


def detect_system_browser(exists=os.path.exists) -> str | None:
    """Return a Playwright channel name ('msedge' | 'chrome') or None."""
    forced = os.environ.get("MULTIPOST_BROWSER", "").strip().lower()
    if forced == "edge":
        return "msedge"
    if forced == "chrome":
        return "chrome"
    if forced == "chromium":
        return None
    if any(exists(p) for p in _EDGE_PATHS):
        return "msedge"
    if any(exists(p) for p in _CHROME_PATHS):
        return "chrome"
    # Non-Windows dev machines: system browsers Playwright can channel to.
    if sys.platform != "win32":
        for cand in ("/usr/bin/microsoft-edge", "/usr/bin/google-chrome",
                     "/usr/bin/google-chrome-stable", "/usr/bin/chromium"):
            if exists(cand):
                return None  # use bundled chromium on dev machines
    return None


def browser_launch_kwargs() -> dict:
    channel = detect_system_browser()
    return {"channel": channel} if channel else {}


def browsers_path() -> str | None:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
        return os.path.join(base, "data", "browsers")
    return None


def ensure_chromium() -> None:
    """Download bundled Chromium ONLY when no system Edge/Chrome is present."""
    global _done
    if _done:
        return
    _done = True
    if detect_system_browser():
        return  # lightweight path: Edge/Chrome already on the machine
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
        # If the download fails, the publisher surfaces Playwright's own
        # "browser not found" error with the manual fix - never hide it here.
        pass

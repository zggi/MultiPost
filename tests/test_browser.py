import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost.bootstrap import browser_launch_kwargs, detect_system_browser  # noqa: E402


def test_edge_preferred_when_installed():
    ch = detect_system_browser(exists=lambda p: "Edge" in p)
    assert ch == "msedge"
    assert browser_launch_kwargs.__name__  # callable sanity


def test_chrome_when_no_edge():
    ch = detect_system_browser(exists=lambda p: "Chrome" in p)
    assert ch == "chrome"


def test_none_when_no_system_browser():
    ch = detect_system_browser(exists=lambda p: False)
    assert ch is None


def test_env_override_chromium(monkeypatch=None):
    os.environ["MULTIPOST_BROWSER"] = "chromium"
    try:
        assert detect_system_browser(exists=lambda p: True) is None
    finally:
        del os.environ["MULTIPOST_BROWSER"]

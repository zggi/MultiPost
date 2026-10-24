import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost import engine  # noqa: E402
from multipost.models import Account  # noqa: E402
from multipost.publishers.base import friendly_error  # noqa: E402


class FakeStore:
    def profile_dir(self, account_id):
        return f"/tmp/profile-{account_id}"

    def load_settings(self):
        return {"proxy": {}}


def test_second_login_while_open_is_skipped():
    acc = Account("tiktok", "TT", "browser")
    calls = []
    release = threading.Event()
    started = threading.Event()

    def fake_open_login(profile_dir):
        calls.append(profile_dir)
        started.set()
        release.wait(timeout=10)

    orig = engine.tiktok_browser.open_login
    engine.tiktok_browser.open_login = fake_open_login
    try:
        t = threading.Thread(target=engine.open_login_for,
                             args=(FakeStore(), acc))
        t.start()
        assert started.wait(timeout=5)
        # Second call while the first window is still open: skipped, no raise.
        engine.open_login_for(FakeStore(), acc)
        assert len(calls) == 1
    finally:
        release.set()
        t.join(timeout=5)
    # After the window closed, login can be opened again.
    release.clear()
    engine.open_login_for(FakeStore(), acc)
    assert len(calls) == 2
    engine.tiktok_browser.open_login = orig


def test_friendly_error_translates_profile_lock():
    msg = friendly_error(RuntimeError(
        "Failed to create a ProcessSingleton for your profile directory"))
    assert msg is not None and "masih terbuka" in msg
    assert friendly_error(RuntimeError("network boom")) is None

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost.publishers.base import dismiss_overlays  # noqa: E402


class FakeLocator:
    def __init__(self, visible):
        self._visible = visible

    @property
    def first(self):
        return self

    def count(self):
        return 1 if self._visible else 0

    def is_visible(self):
        return self._visible

    def locator(self, _sel):
        return FakeLocator(False)

    def click(self, timeout=None):
        pass


class FakeKeyboard:
    def press(self, _key):
        pass


class FakePage:
    def __init__(self, overlay_visible):
        self._ov = overlay_visible
        self.keyboard = FakeKeyboard()

    def locator(self, _sel):
        return FakeLocator(self._ov)

    def wait_for_timeout(self, _ms):
        pass


def test_no_overlay_returns_true_at_once():
    assert dismiss_overlays(FakePage(False), seconds=2) is True


def test_overlay_that_never_closes_times_out_false():
    # Portal visible, but its buttons never match and Escape does nothing in
    # the fake - the helper must give up after the deadline, not hang forever.
    import time
    start = time.time()
    assert dismiss_overlays(FakePage(True), seconds=1) is False
    assert time.time() - start < 10

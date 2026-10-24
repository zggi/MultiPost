import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost.captions import adapt  # noqa: E402
from multipost.models import Account, Job  # noqa: E402
from multipost.publishers import custom_browser as custom_pub  # noqa: E402


class FakeKeyboard:
    def __init__(self):
        self.typed = []

    def press(self, keys):
        self.typed.append(("press", keys))

    def type(self, text, delay=0):
        self.typed.append(("type", text))


class FakeLocator:
    def __init__(self, selector, tag="TEXTAREA"):
        self.selector = selector
        self.tag = tag
        self.calls = []

    @property
    def first(self):
        return self

    def set_input_files(self, path, timeout=None):
        self.calls.append(("set_input_files", path))

    def wait_for(self, state=None, timeout=None):
        self.calls.append(("wait_for", state))

    def evaluate(self, script):
        return self.tag

    def fill(self, text):
        self.calls.append(("fill", text))

    def click(self, timeout=None, force=False):
        self.calls.append(("click",))


class FakePage:
    def __init__(self, tag="TEXTAREA"):
        self.tag = tag
        self.calls = []
        self.keyboard = FakeKeyboard()
        self.locators = {}

    def goto(self, url, wait_until=None, timeout=None):
        self.calls.append(("goto", url))

    def wait_for_timeout(self, ms):
        self.calls.append(("wait", ms))

    def locator(self, selector):
        loc = FakeLocator(selector, self.tag)
        self.locators[selector] = loc
        return loc

    def screenshot(self, path=None):
        self.calls.append(("screenshot", path))


class FakeCtx:
    def __init__(self, page):
        self.pages = [page]

    def new_page(self):
        return self.pages[0]

    def close(self):
        pass


class FakePW:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _run_publish(tag, extra):
    """Fake the lazy `from playwright.sync_api import sync_playwright` import
    (playwright is not installed in this VM) plus the browser launch."""
    import types

    import multipost.publishers.base as b
    import multipost.publishers.custom_browser as m

    page = FakePage(tag=tag)
    ctx = FakeCtx(page)
    fake_api = types.ModuleType("playwright.sync_api")
    fake_api.sync_playwright = lambda: FakePW()
    fake_pkg = types.ModuleType("playwright")
    fake_pkg.sync_api = fake_api
    sys.modules["playwright"] = fake_pkg
    sys.modules["playwright.sync_api"] = fake_api
    m_launch = m.launch_persistent
    m.launch_persistent = lambda p, d, headless=False, proxy=None: ctx  # noqa: E731
    m.dismiss_overlays = lambda page, seconds=20: False  # noqa: E731
    try:
        acc = Account(platform="custom", label="Toko", mode="browser", extra=extra)
        job = Job(video_path="/tmp/v.mp4", caption="halo", account_ids=[acc.id])
        # require_file needs a real file; point at this test file instead.
        job.video_path = os.path.abspath(__file__)
        res = custom_pub.publish(acc, job, "halo", "/tmp/prof", "/tmp/logs")
    finally:
        m.launch_persistent = m_launch
        m.dismiss_overlays = b.dismiss_overlays
        del sys.modules["playwright"]
        del sys.modules["playwright.sync_api"]
    return res, page


def test_adapt_custom_passthrough():
    long_caption = "x" * 5000
    ad = adapt("custom", long_caption)
    assert ad.text == long_caption
    assert ad.warnings == []


def test_config_defaults_when_selectors_blank():
    acc = Account(platform="custom", label="Toko", mode="browser",
                  extra={"custom_upload_url": "https://contoh.com/upload"})
    cfg = custom_pub.config(acc)
    assert cfg["file_selector"] == custom_pub.DEFAULT_FILE_SELECTOR
    assert cfg["caption_selector"] == custom_pub.DEFAULT_CAPTION_SELECTOR
    assert cfg["publish_selector"] == custom_pub.DEFAULT_PUBLISH_SELECTOR


def test_publish_textarea_uses_fill_and_clicks_publish():
    extra = {"custom_upload_url": "https://contoh.com/upload",
             "custom_file_selector": "input.up",
             "custom_caption_selector": "textarea.cap",
             "custom_publish_selector": "button.go"}
    res, page = _run_publish("TEXTAREA", extra)
    assert res.status == "success"
    assert ("goto", "https://contoh.com/upload") in page.calls
    cap = page.locators["textarea.cap"]
    assert ("fill", "halo") in cap.calls
    assert ("click",) in page.locators["button.go"].calls
    assert ("set_input_files", os.path.abspath(__file__)) in \
        page.locators["input.up"].calls


def test_publish_contenteditable_types_text():
    extra = {"custom_upload_url": "https://contoh.com/upload"}
    res, page = _run_publish("DIV", extra)
    assert res.status == "success"
    assert ("type", "halo") in page.keyboard.typed


def test_publish_without_url_is_error_not_crash():
    acc = Account(platform="custom", label="Toko", mode="browser", extra={})
    job = Job(video_path="/tmp/v.mp4", caption="halo", account_ids=[acc.id])
    res = custom_pub.publish(acc, job, "halo", "/tmp/prof", "/tmp/logs")
    assert res.status == "error"
    assert "URL" in res.message


def test_account_roundtrip_keeps_custom_extra():
    acc = Account(platform="custom", label="Toko", mode="browser",
                  extra={"custom_name": "Toko",
                         "custom_upload_url": "https://contoh.com/upload",
                         "custom_file_selector": "input.up"})
    restored = Account.from_dict(acc.to_dict())
    assert restored.extra == acc.extra
    assert custom_pub.config(restored)["name"] == "Toko"

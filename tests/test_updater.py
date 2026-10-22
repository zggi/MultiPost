import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost.models import media_kind  # noqa: E402
from multipost.updater import is_newer, parse_version, pick_setup_asset  # noqa: E402


def test_parse_version_variants():
    assert parse_version("v1.4.0") == (1, 4, 0)
    assert parse_version("1.3.1") == (1, 3, 1)
    assert parse_version("v2") == (2, 0, 0)


def test_is_newer_compares_numerically():
    assert is_newer("1.3.1", "1.4.0") is True
    assert is_newer("1.4.0", "1.4.0") is False
    assert is_newer("1.10.0", "1.9.9") is False  # numeric, not lexicographic


def test_pick_setup_asset_by_name():
    release = {"assets": [
        {"name": "MultiPost-Portable.zip", "size": 5, "browser_download_url": "u1"},
        {"name": "MultiPost-Setup.exe", "id": 42, "size": 9, "browser_download_url": "u2"},
    ]}
    asset = pick_setup_asset(release)
    assert asset["url"] == "u2" and asset["size"] == 9 and asset["id"] == 42
    assert pick_setup_asset({"assets": []}) is None


def test_download_sources_api_route_first():
    from multipost.updater import download_sources
    src = download_sources({"id": 42, "url": "https://github.com/x/y.exe"})
    assert "api.github.com" in src[0][0] and "/assets/42" in src[0][0]
    assert src[0][1]["Accept"] == "application/octet-stream"
    assert src[1][0] == "https://github.com/x/y.exe"
    # Without an asset id only the plain URL route remains.
    assert len(download_sources({"url": "https://github.com/x/y.exe"})) == 1


def test_download_setup_falls_back_to_second_route():
    import multipost.updater as up

    class FakeResp:
        headers = {"Content-Length": "2000000"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=1):
            yield b"x" * 2_000_000

    calls = []

    class FakeRequests:
        @staticmethod
        def get(url, **kw):
            calls.append(url)
            if "api.github.com" in url:
                raise ConnectionError("jalur API putus")
            return FakeResp()

    orig = up.requests
    up.requests = FakeRequests
    try:
        seen = []
        path = up.download_setup({"id": 7, "tag": "v9.9.9",
                                  "url": "https://github.com/zggi/x.exe"},
                                 progress=lambda d, t: seen.append((d, t)))
    finally:
        up.requests = orig
    import os
    assert len(calls) == 2 and "api.github.com" in calls[0]
    assert os.path.getsize(path) == 2_000_000
    assert seen and seen[-1] == (2_000_000, 2_000_000)
    os.unlink(path)


def test_media_kind_image_and_video():
    assert media_kind("foto.JPG") == "image"
    assert media_kind("promo.png") == "image"
    assert media_kind("clip.mp4") == "video"
    assert media_kind("") == "video"

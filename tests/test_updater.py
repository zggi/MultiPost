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
        {"name": "MultiPost-Setup.exe", "size": 9, "browser_download_url": "u2"},
    ]}
    asset = pick_setup_asset(release)
    assert asset["url"] == "u2" and asset["size"] == 9
    assert pick_setup_asset({"assets": []}) is None


def test_media_kind_image_and_video():
    assert media_kind("foto.JPG") == "image"
    assert media_kind("promo.png") == "image"
    assert media_kind("clip.mp4") == "video"
    assert media_kind("") == "video"

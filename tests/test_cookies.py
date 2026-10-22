import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost.models import Account  # noqa: E402
from multipost.publishers.base import parse_cookies  # noqa: E402


def test_single_session_cookie():
    acc = Account(platform="tiktok", label="t", mode="cookie", secret="abc123",
                  extra={"cookie_name": "sessionid", "cookie_domain": ".tiktok.com"})
    cookies = parse_cookies(acc)
    assert cookies == [{"name": "sessionid", "value": "abc123",
                        "domain": ".tiktok.com", "path": "/"}]


def test_cookie_editor_json_export():
    import json
    export = json.dumps([
        {"name": "c_user", "value": "1000", "domain": ".facebook.com", "path": "/"},
        {"name": "xs", "value": "xyz", "domain": ".facebook.com", "path": "/"},
        {"name": "", "value": "skip-me"},
    ])
    acc = Account(platform="facebook", label="f", mode="cookie", secret=export)
    cookies = parse_cookies(acc)
    assert [c["name"] for c in cookies] == ["c_user", "xs"]


def test_empty_secret_no_cookies():
    acc = Account(platform="tiktok", label="t", mode="cookie", secret="")
    assert parse_cookies(acc) == []

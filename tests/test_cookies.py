import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost.models import Account  # noqa: E402
from multipost.publishers.base import parse_cookies  # noqa: E402


def test_single_session_cookie():
    acc = Account(platform="tiktok", label="t", mode="cookie", secret="abc123",
                  extra={"cookie_name": "sessionid", "cookie_domain": ".tiktok.com"})
    cookies = parse_cookies(acc)
    # TikTok session token rides on 3 companion cookies with the same value.
    assert [c["name"] for c in cookies] == ["sessionid", "sessionid_ss", "sid_tt"]
    assert all(c["value"] == "abc123" and c["domain"] == ".tiktok.com"
               and c["path"] == "/" for c in cookies)


def test_pasted_full_cookie_header_is_split():
    acc = Account(platform="tiktok", label="t", mode="cookie",
                  secret="sessionid=tok123; sid_tt=tok123; uid_tt=zz",
                  extra={"cookie_name": "sessionid", "cookie_domain": ".tiktok.com"})
    got = {c["name"]: c["value"] for c in parse_cookies(acc)}
    assert got == {"sessionid": "tok123", "sid_tt": "tok123", "uid_tt": "zz"}


def test_value_with_name_prefix_is_cleaned():
    acc = Account(platform="tiktok", label="t", mode="cookie",
                  secret="sessionid=tok999",
                  extra={"cookie_name": "sessionid", "cookie_domain": ".tiktok.com"})
    cookies = parse_cookies(acc)
    assert cookies[0]["value"] == "tok999"


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

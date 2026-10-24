import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost.interval import describe, next_delay  # noqa: E402
from multipost.proxy import (is_active, normalize, playwright_proxy,  # noqa: E402
                             requests_proxies, server_url)
from multipost.store import Store  # noqa: E402


def test_delay_fixed():
    assert next_delay(60, False) == 60
    assert next_delay(0, True) == 0
    assert next_delay(-5, True) == 0


def test_delay_random_within_half_to_one_and_half():
    rng = random.Random(42)
    for _ in range(50):
        d = next_delay(60, True, rng=rng)
        assert 30 <= d <= 90
    assert describe(60, True) == "jeda acak 30–90 dtk"
    assert describe(60, False) == "jeda 60 dtk"
    assert describe(0, True) == "tanpa jeda"


def test_proxy_inactive_by_default():
    assert not is_active(None)
    assert not is_active({"enabled": True, "host": "", "port": 8080})
    assert server_url(None) is None
    assert requests_proxies(None) == {}
    assert playwright_proxy(None) is None


def test_proxy_builders_with_auth():
    cfg = {"enabled": True, "type": "socks5", "host": "1.2.3.4", "port": 1080,
           "username": "u", "password": "p@ss"}
    assert server_url(cfg) == "socks5://1.2.3.4:1080"
    rp = requests_proxies(cfg)
    assert rp["http"] == "socks5://u:p%40ss@1.2.3.4:1080"
    pp = playwright_proxy(cfg)
    assert pp == {"server": "socks5://1.2.3.4:1080", "username": "u", "password": "p@ss"}
    assert normalize(cfg)["type"] == "socks5"


def test_settings_roundtrip(tmp_path):
    store = Store(str(tmp_path))
    settings = store.load_settings()
    assert settings["interval_seconds"] == 60 and settings["interval_random"] is True
    assert settings["proxy"]["enabled"] is False
    settings["interval_seconds"] = 120
    settings["proxy"] = {"enabled": True, "type": "http", "host": "9.9.9.9",
                         "port": 3128, "username": "a", "password": "secret"}
    store.save_settings(settings)
    reloaded = Store(str(tmp_path)).load_settings()
    assert reloaded["interval_seconds"] == 120
    assert reloaded["proxy"]["host"] == "9.9.9.9"
    assert reloaded["proxy"]["password"] == "secret"  # encrypted on disk, decrypted here
    raw = open(str(tmp_path) + "/settings.json", encoding="utf-8").read()
    assert "secret" not in raw  # never stored in plain text

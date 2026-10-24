"""Optional global proxy support (HTTP / SOCKS5, with optional auth).

One proxy for the whole app: it is used by the Playwright browser contexts
(browser/cookie publishers) AND by the Meta API requests. Leave it OFF unless
you need it (e.g. one account per IP) - a proxy adds a failure point, and a
dead proxy blocks every publish.

Settings shape (stored by Store, password encrypted like account secrets):
    {"enabled": bool, "type": "http"|"socks5", "host": str, "port": int,
     "username": str, "password": str}
"""

from __future__ import annotations

from urllib.parse import quote

DEFAULTS = {"enabled": False, "type": "http", "host": "", "port": 8080,
            "username": "", "password": ""}


def normalize(settings: dict | None) -> dict:
    out = dict(DEFAULTS)
    if settings:
        out.update({k: v for k, v in settings.items() if k in DEFAULTS})
    return out


def is_active(settings: dict | None) -> bool:
    s = normalize(settings)
    return bool(s["enabled"] and s["host"] and s["port"])


def server_url(settings: dict | None) -> str | None:
    """'http://host:port' or 'socks5://host:port' (no credentials)."""
    s = normalize(settings)
    if not is_active(settings):
        return None
    return f"{s['type']}://{s['host']}:{s['port']}"


def requests_proxies(settings: dict | None) -> dict:
    """proxies dict for requests, or {} when inactive."""
    s = normalize(settings)
    if not is_active(settings):
        return {}
    auth = ""
    if s["username"]:
        auth = f"{quote(s['username'], safe='')}:{quote(s['password'], safe='')}@"
    url = f"{s['type']}://{auth}{s['host']}:{s['port']}"
    return {"http": url, "https": url}


def playwright_proxy(settings: dict | None) -> dict | None:
    """proxy dict for Playwright launch_persistent_context, or None."""
    s = normalize(settings)
    if not is_active(settings):
        return None
    proxy = {"server": f"{s['type']}://{s['host']}:{s['port']}"}
    if s["username"]:
        proxy["username"] = s["username"]
        proxy["password"] = s["password"]
    return proxy

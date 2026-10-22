"""Shared publisher plumbing."""

from __future__ import annotations

import os

from ..models import Account, PublishResult


class PublishError(Exception):
    """A user-readable publish failure (shown in the UI as-is)."""


def fail(account: Account, message: str) -> PublishResult:
    return PublishResult(account.platform, account.label, "failed", message)


def ok(account: Account, message: str, url: str = "") -> PublishResult:
    return PublishResult(account.platform, account.label, "success", message, url)


def require_file(path: str) -> None:
    if not path or not os.path.isfile(path):
        raise PublishError(f"File video tidak ditemukan: {path!r}. Pilih file dulu.")


def launch_persistent(playwright, profile_dir: str, headless: bool = False):
    """Persistent Chromium context: this folder IS the login session ('cookie'
    mode without ever copying raw cookie strings around)."""
    from ..bootstrap import browser_launch_kwargs, ensure_chromium

    ensure_chromium()
    return playwright.chromium.launch_persistent_context(
        profile_dir,
        headless=headless,
        viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
        **browser_launch_kwargs(),
    )


def parse_cookies(account: Account) -> list[dict]:
    """Normalise whatever the user saved into Playwright cookie dicts.

    Two accepted shapes:
    1. A single raw value (e.g. TikTok 'sessionid') - uses the account's
       cookie_name / cookie_domain.
    2. A JSON array exported by Cookie-Editor ("Export > JSON") - needed for
       Facebook, which requires several cookies together (c_user + xs + ...).
    """
    secret = (account.secret or "").strip()
    if not secret:
        return []
    if secret.startswith("["):
        import json

        cookies = []
        for item in json.loads(secret):
            if not item.get("name") or "value" not in item:
                continue
            cookies.append({
                "name": item["name"], "value": str(item["value"]),
                "domain": item.get("domain") or account.extra.get("cookie_domain", ""),
                "path": item.get("path") or "/",
            })
        return cookies
    name = account.extra.get("cookie_name") or "sessionid"
    domain = account.extra.get("cookie_domain") or ".tiktok.com"
    return [{"name": name, "value": secret, "domain": domain, "path": "/"}]


def dismiss_overlays(page, seconds: float = 20) -> bool:
    """Close modal/popups that intercept clicks (TikTok/YouTube render them in
    a floating-ui portal on top of everything - Playwright then retries the
    click forever: 'subtree intercepts pointer events').

    Strategy: if a dialog/portal is visible, click its primary button
    (Post/Confirm/Continue/...), else press Escape. Returns True when no
    overlay remains. Safe to call when nothing is open (returns at once).
    """
    import time

    candidates = ["Post", "Publish", "Confirm", "Continue", "OK", "Got it",
                  "Not now", "Discard", "Close", "Konfirmasi", "Lanjutkan",
                  "Tutup", "Simpan", "Ya"]
    deadline = time.time() + seconds
    while True:
        portal = page.locator(
            "[data-floating-ui-portal], div[role='dialog'], "
            "div[role='alertdialog']").first
        try:
            visible = portal.count() > 0 and portal.is_visible()
        except Exception:
            visible = False
        if not visible:
            return True
        clicked = False
        for text in candidates:
            btn = portal.locator(f"button:has-text('{text}')").first
            try:
                if btn.count() > 0 and btn.is_visible():
                    btn.click(timeout=1200)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
        if time.time() >= deadline:
            return False
        page.wait_for_timeout(700)


def apply_raw_cookie(context, account: Account) -> None:
    """Cookie mode: inject the cookie(s) the user saved into the context."""
    cookies = parse_cookies(account)
    if cookies:
        context.add_cookies(cookies)

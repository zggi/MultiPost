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


def launch_persistent(playwright, profile_dir: str, headless: bool = False,
                      proxy: dict | None = None):
    """Persistent Chromium context: this folder IS the login session ('cookie'
    mode without ever copying raw cookie strings around).

    proxy: Playwright proxy dict from multipost.proxy.playwright_proxy, or
    None for a direct connection.
    """
    from ..bootstrap import browser_launch_kwargs, ensure_chromium

    ensure_chromium()
    kwargs = dict(
        headless=headless,
        viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
        **browser_launch_kwargs(),
    )
    if proxy:
        kwargs["proxy"] = proxy
    return playwright.chromium.launch_persistent_context(profile_dir, **kwargs)


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
    # Pasted a full Cookie header ("sessionid=abc; sid_tt=abc; ...")? Split it
    # into individual cookies instead of treating the whole string as a value.
    if ";" in secret and "=" in secret.split(";")[0]:
        cookies = []
        for pair in secret.split(";"):
            if "=" not in pair:
                continue
            k, v = pair.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and v:
                cookies.append({"name": k, "value": v,
                                "domain": domain, "path": "/"})
        if cookies:
            return cookies
    value = secret
    if value.lower().startswith(f"{name.lower()}="):
        value = value[len(name) + 1:]
    cookies = [{"name": name, "value": value, "domain": domain, "path": "/"}]
    # TikTok's web session rides on companion cookies holding the same token:
    # sessionid alone is often rejected by TikTok Studio (login page), while
    # sessionid + sessionid_ss + sid_tt together are accepted.
    if name == "sessionid" and "tiktok" in domain:
        for companion in ("sessionid_ss", "sid_tt"):
            cookies.append({"name": companion, "value": value,
                            "domain": domain, "path": "/"})
    return cookies


_OVERLAY_SEL = ("[data-floating-ui-portal], div[role='dialog'], "
                "div[role='alertdialog'], .TUXModal-overlay")
_OVERLAY_TEXTS = ["Post", "Publish", "Confirm", "Continue", "OK", "Got it",
                 "Not now", "I'm aware", "Understood", "Agree", "Accept",
                 "Discard", "Close", "Konfirmasi", "Lanjutkan", "Mengerti",
                 "Setuju", "Tutup", "Simpan", "Ya", "OK, got it"]


def _first_visible_overlay(page):
    loc = page.locator(_OVERLAY_SEL)
    try:
        n = loc.count()
    except Exception:
        return None
    for i in range(min(n, 6)):
        try:
            el = loc.nth(i)
            if el.count() > 0 and el.is_visible():
                # A portal container with no visible dialog child is harmless.
                inner = el.locator(
                    "[role='dialog'], [class*='modal'], [class*='Modal']")
                has_inner = False
                try:
                    for j in range(min(inner.count(), 4)):
                        if inner.nth(j).is_visible():
                            has_inner = True
                            break
                except Exception:
                    has_inner = False
                try:
                    height = el.evaluate("e => e.getBoundingClientRect().height")
                except Exception:
                    height = 999  # cannot measure -> treat as a real overlay
                if height > 60 or has_inner:
                    return el
        except Exception:
            continue
    return None


def _click_overlay_button(overlay) -> str | None:
    """Click the dialog's primary/close button. Returns its label or None."""
    for text in _OVERLAY_TEXTS:
        btn = overlay.locator(f"button:has-text('{text}')").first
        try:
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=1200)
                return text
        except Exception:
            continue
    # Icon-only close buttons (X) carry an aria-label instead of text.
    for sel in ("button[aria-label*='close' i]", "button[aria-label*='tutup' i]",
                "[class*='close'] button", "button[class*='close' i]"):
        btn = overlay.locator(sel).first
        try:
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=1200)
                return "X (tutup)"
        except Exception:
            continue
    # Last resort: a dialog with exactly ONE visible button - that button is
    # the way out (notice/acknowledge dialogs), unless it would destroy work.
    try:
        buttons = overlay.locator("button")
        visible = []
        for i in range(min(buttons.count(), 8)):
            b = buttons.nth(i)
            if b.is_visible():
                visible.append(b)
        if len(visible) == 1:
            label = (visible[0].inner_text() or "").strip()
            if label.lower() not in ("delete", "hapus", "start over", "mulai ulang"):
                visible[0].click(timeout=1200)
                return label or "(tombol tunggal)"
    except Exception:
        pass
    return None


def dismiss_overlays(page, seconds: float = 20) -> bool:
    """Close modal/popups that intercept clicks (TikTok floats a TUXModal in a
    portal over the whole upload page - Playwright then retries clicks into a
    30s timeout: 'subtree intercepts pointer events').

    Works at ANY step, not just the Post button. Returns True when no overlay
    remains. Safe to call when nothing is open (returns at once).
    """
    import time

    deadline = time.time() + seconds
    while True:
        overlay = _first_visible_overlay(page)
        if overlay is None:
            return True
        label = _click_overlay_button(overlay)
        if label:
            print(f"   popup ditutup: tombol '{label}'")
        else:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
        if time.time() >= deadline:
            return _first_visible_overlay(page) is None
        page.wait_for_timeout(700)


def apply_raw_cookie(context, account: Account) -> None:
    """Cookie mode: inject the cookie(s) the user saved into the context."""
    cookies = parse_cookies(account)
    if cookies:
        context.add_cookies(cookies)


def friendly_error(e: Exception) -> str | None:
    """Translate cryptic Chromium launch errors into guidance, else None."""
    text = str(e)
    if "ProcessSingleton" in text or "already in use" in text \
            or "Opening in existing browser session" in text:
        return ("Profil browser akun ini masih terbuka di jendela lain "
                "(jendela Login atau publish yang belum ditutup). Tutup "
                "jendela Edge MultiPost untuk akun ini, lalu coba lagi.")
    return None

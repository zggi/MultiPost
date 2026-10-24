"""Generic custom platform (v1.7.0): the user defines the platform themselves
in the Akun tab - upload-page URL plus CSS selectors for the file input,
the caption field and the publish button. Publishing is browser automation
through the account's persistent profile (same session model as TikTok /
YouTube), so the user logs in once via "Login Browser" and the session is
reused.

Honest limitation: a generic flow cannot know what "success" looks like on
an arbitrary site, so after clicking the publish button we screenshot the
page into data/logs and report success-with-verification-note. The user
should eyeball the site once for a new custom platform; if the click did
not post, the selectors need adjusting.
"""

from __future__ import annotations

import os
import time

from ..models import Account, Job, PublishResult
from .base import (PublishError, dismiss_overlays, fail, friendly_error,
                   launch_persistent, ok, require_file)

DEFAULT_FILE_SELECTOR = "input[type='file']"
DEFAULT_CAPTION_SELECTOR = "textarea, [contenteditable='true']"
DEFAULT_PUBLISH_SELECTOR = ("button:has-text('Posting'), button:has-text('Publish'), "
                            "button[type='submit']")


def config(account: Account) -> dict:
    """Resolve a custom platform's config from the account's extra dict,
    filling in the defaults for any selector the user left blank."""
    extra = account.extra or {}
    return {
        "name": (extra.get("custom_name") or account.label or "Custom").strip(),
        "upload_url": (extra.get("custom_upload_url") or "").strip(),
        "file_selector": (extra.get("custom_file_selector") or DEFAULT_FILE_SELECTOR).strip(),
        "caption_selector": (extra.get("custom_caption_selector") or DEFAULT_CAPTION_SELECTOR).strip(),
        "publish_selector": (extra.get("custom_publish_selector") or DEFAULT_PUBLISH_SELECTOR).strip(),
    }


def open_login(account: Account, profile_dir: str,
               proxy: dict | None = None) -> None:
    """Open the custom upload page in the account's profile so the user can
    log in there (and inspect the page's selectors with F12 if needed)."""
    from playwright.sync_api import sync_playwright

    cfg = config(account)
    if not cfg["upload_url"]:
        raise PublishError(
            "URL halaman upload platform custom belum diisi (tab Akun).")
    with sync_playwright() as p:
        ctx = launch_persistent(p, profile_dir, headless=False, proxy=proxy)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(cfg["upload_url"], wait_until="domcontentloaded", timeout=60_000)
        print("   jendela login custom terbuka - login di sana, lalu tutup jendelanya.")
        for _ in range(60):
            time.sleep(5)
            try:
                if page.is_closed():
                    break
            except Exception:
                break
        ctx.close()


def publish(account: Account, job: Job, caption: str, profile_dir: str,
            logs_dir: str, proxy: dict | None = None) -> PublishResult:
    cfg = config(account)
    if not cfg["upload_url"]:
        return fail(account, "URL halaman upload platform custom belum diisi "
                             "(tab Akun > platform custom).")
    try:
        require_file(job.video_path)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            ctx = launch_persistent(p, profile_dir, headless=False, proxy=proxy)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(cfg["upload_url"], wait_until="domcontentloaded",
                          timeout=90_000)
                page.wait_for_timeout(3000)
                dismiss_overlays(page, seconds=10)
                file_input = page.locator(cfg["file_selector"]).first
                file_input.set_input_files(job.video_path, timeout=60_000)
                page.wait_for_timeout(2000)
                editor = page.locator(cfg["caption_selector"]).first
                editor.wait_for(state="visible", timeout=60_000)
                try:
                    tag = (editor.evaluate("e => e.tagName") or "").upper()
                except Exception:
                    tag = ""
                if tag in ("TEXTAREA", "INPUT"):
                    editor.fill(caption)
                else:
                    editor.click(timeout=10_000)
                    page.keyboard.press("Control+A")
                    page.keyboard.type(caption, delay=5)
                post_btn = page.locator(cfg["publish_selector"]).first
                post_btn.wait_for(state="visible", timeout=60_000)
                post_btn.click(timeout=10_000)
                page.wait_for_timeout(5000)
                shot = ""
                try:
                    os.makedirs(logs_dir, exist_ok=True)
                    shot = os.path.join(
                        logs_dir, f"custom-{account.id}-{int(time.time())}.png")
                    page.screenshot(path=shot)
                except Exception:
                    shot = ""
                return ok(account,
                          f"Tombol posting '{cfg['name']}' sudah diklik. "
                          "Karena tiap situs beda, verifikasi sekali di situs "
                          "apakah postingan sudah tayang; bila belum, "
                          "sesuaikan selector di tab Akun."
                          + (f" Bukti layar: {shot}" if shot else ""))
            finally:
                ctx.close()
    except Exception as e:  # noqa: BLE001 - surfaced to the user as a result
        friendly = friendly_error(e)
        return fail(account, friendly or str(e))

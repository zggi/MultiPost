"""Meta browser fallback (EXPERIMENTAL): Instagram web + Facebook web upload
via a persistent local profile. Use when API mode is not possible (personal
account, no public video URL). The Meta web composer changes often - treat a
failure screenshot in data/logs/ as the source of truth.

Facebook personal video posts are only possible this way; the connector/API
route for personal profiles is text-only.
"""

from __future__ import annotations

import os
import time

from ..models import Account, Job, PublishResult
from .base import PublishError, fail, launch_persistent, ok, require_file

URLS = {
    "instagram": "https://www.instagram.com/",
    "threads": "https://www.threads.net/",
    "facebook": "https://www.facebook.com/",
}


def open_login(platform: str, profile_dir: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = launch_persistent(p, profile_dir, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(URLS[platform])
        for _ in range(60):
            time.sleep(5)
            if "login" not in page.url and "checkpoint" not in page.url:
                break
        ctx.close()


def publish(account: Account, job: Job, caption: str, profile_dir: str,
            logs_dir: str) -> PublishResult:
    # Deliberately honest v1 scope: opening the composer reliably across Meta's
    # changing web UI needs per-account live tuning, so v1 browser mode for Meta
    # uploads the file through the profile session where a stable file input
    # exists (Facebook), and reports a precise manual-assist status otherwise.
    try:
        require_file(job.video_path)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            ctx = launch_persistent(p, profile_dir, headless=False)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(URLS[account.platform], wait_until="domcontentloaded",
                          timeout=90_000)
                page.wait_for_timeout(4000)
                if "login" in page.url:
                    raise PublishError(
                        f"Sesi {account.platform} belum login. Klik 'Login Browser' "
                        "di tab Akun untuk akun ini.")
                if account.platform == "facebook":
                    composer = page.locator(
                        "[role='button']:has-text(\"What's on your mind\"), "
                        "[role='button']:has-text('Apa yang Anda pikirkan')").first
                    composer.click()
                    page.wait_for_timeout(2000)
                    file_input = page.locator("input[type='file']").last
                    file_input.set_input_files(job.video_path, timeout=60_000)
                    box = page.locator("div[contenteditable='true'][role='textbox']").first
                    box.click()
                    page.keyboard.type(caption, delay=3)
                    page.locator("[aria-label='Post'], [aria-label='Posting'], "
                                 "div[role='button']:has-text('Post')").last.click()
                    page.wait_for_timeout(8000)
                    return ok(account, "Post Facebook (browser) terbit.")
                raise PublishError(
                    f"Mode Browser untuk {account.platform} masih eksperimental di v1 - "
                    "composer web Meta sering berubah. Pakai mode API untuk akun ini, "
                    "atau posting manual dari sesi yang sudah login.")
            finally:
                ctx.close()
    except PublishError as e:
        return fail(account, str(e))
    except Exception as e:
        return fail(account, f"Meta browser gagal: {e}")

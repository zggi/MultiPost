"""YouTube Shorts publisher via YouTube Studio in a persistent local profile.

Why browser, not the Data API: uploads from an unaudited Google Cloud project
are forced to PRIVATE by Google. Studio uploads publish publicly, like a human.
Same automation caveat as TikTok: human rhythm, selectors can drift, failures
screenshot to data/logs/.
"""

from __future__ import annotations

import os
import time

from ..models import Account, Job, PublishResult
from .base import (PublishError, apply_raw_cookie, dismiss_overlays, fail,
                   friendly_error, launch_persistent, ok, require_file)

STUDIO_URL = "https://studio.youtube.com"
LOGIN_URL = "https://accounts.google.com/ServiceLogin?service=youtube"


def open_login(profile_dir: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = launch_persistent(p, profile_dir, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(LOGIN_URL)
        for _ in range(60):
            time.sleep(5)
            if "studio.youtube.com" in page.url or "myaccount.google.com" in page.url:
                break
        ctx.close()


def publish(account: Account, job: Job, title: str, description: str,
            profile_dir: str, logs_dir: str) -> PublishResult:
    if job.kind == "image":
        # Honest platform limit: YouTube uploads are video-only (community
        # image posts need a 500+ subscriber channel and a different flow).
        return PublishResult(account.platform, account.label, "skipped",
                             "YouTube tidak menerima posting gambar (khusus video/Shorts) - dilewati.")
    try:
        require_file(job.video_path)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            ctx = launch_persistent(p, profile_dir, headless=False)
            try:
                if account.mode == "cookie":
                    account.extra.setdefault("cookie_domain", ".youtube.com")
                    apply_raw_cookie(ctx, account)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(STUDIO_URL, wait_until="domcontentloaded", timeout=90_000)
                page.wait_for_timeout(4000)
                if "accounts.google.com" in page.url:
                    raise PublishError(
                        "Sesi YouTube belum login / kedaluwarsa. "
                        "Klik 'Login Browser' di tab Akun untuk akun ini.")
                page.locator("#create-icon, ytcp-button:has-text('Create')").first.click()
                page.locator("tp-yt-paper-item:has-text('Upload video'), "
                             "#text-item-0").first.click()
                file_input = page.locator("input[type='file']").first
                file_input.set_input_files(job.video_path, timeout=60_000)
                title_box = page.locator(
                    "ytcp-social-suggestions-textbox#title-textarea #textbox, "
                    "#title-textarea #textbox").first
                title_box.wait_for(state="visible", timeout=120_000)
                title_box.click()
                page.keyboard.press("Control+A")
                page.keyboard.type(title, delay=5)
                desc_box = page.locator(
                    "#description-textarea #textbox").first
                if description:
                    desc_box.click()
                    page.keyboard.type(description, delay=2)
                # Details -> Next (audience step), default: not made for kids.
                not_kids = page.locator(
                    "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']").first
                if not_kids.count():
                    not_kids.click()
                for _ in range(3):
                    page.locator("#next-button").first.click()
                    page.wait_for_timeout(2500)
                public_radio = page.locator(
                    "tp-yt-paper-radio-button[name='PUBLIC']").first
                public_radio.wait_for(state="visible", timeout=60_000)
                public_radio.click()
                dismiss_overlays(page, seconds=10)
                page.locator("#done-button").first.click(timeout=30_000)
                page.wait_for_timeout(8000)
                return ok(account, "Video YouTube terbit sebagai publik "
                                   "(video vertikal <=3 menit otomatis jadi Shorts).",
                          "https://studio.youtube.com")
            except PublishError as e:
                try:
                    os.makedirs(logs_dir, exist_ok=True)
                    shot = os.path.join(logs_dir, f"youtube-error-{int(time.time())}.png")
                    ctx.pages[0].screenshot(path=shot)
                    raise PublishError(f"{e} Screenshot: {shot}")
                except PublishError:
                    raise
                except Exception:
                    raise e
            finally:
                ctx.close()
    except PublishError as e:
        return fail(account, str(e))
    except Exception as e:
        return fail(account, friendly_error(e) or f"YouTube browser gagal: {e}")

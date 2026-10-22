"""TikTok publisher via TikTok Studio in a persistent local browser profile.

Why browser, not the official API: an unaudited TikTok API client can only
post PRIVATE (SELF_ONLY) videos, and TikTok's audit rejects personal
utility tools. The browser session posts publicly, exactly like a human.

Risk note: this is automation of a web UI. Keep a human rhythm
(1-3 posts/day/account); mass posting can trigger limits / checkpoints.
Selectors drift when TikTok changes its UI - failures screenshot to
data/logs/ so the breakage is visible, never silent.
"""

from __future__ import annotations

import os
import time

from ..models import Account, Job, PublishResult
from .base import (PublishError, apply_raw_cookie, dismiss_overlays, fail,
                   friendly_error, launch_persistent, ok, require_file)

UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"
LOGIN_URL = "https://www.tiktok.com/login"


def open_login(profile_dir: str) -> None:
    """Open a headed browser so the USER logs in themselves (password, OTP and
    CAPTCHA stay between the user and TikTok). Session persists in profile_dir."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = launch_persistent(p, profile_dir, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(LOGIN_URL)
        # Give the user up to 5 minutes to finish logging in.
        for _ in range(60):
            time.sleep(5)
            if "login" not in page.url:
                break
        ctx.close()


def _screenshot(ctx, data_hint: str) -> str:
    try:
        os.makedirs(data_hint, exist_ok=True)
        path = os.path.join(data_hint, f"tiktok-error-{int(time.time())}.png")
        ctx.pages[0].screenshot(path=path)
        return path
    except Exception:
        return ""


def publish(account: Account, job: Job, caption: str, profile_dir: str,
            logs_dir: str) -> PublishResult:
    try:
        require_file(job.video_path)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            ctx = launch_persistent(p, profile_dir, headless=False)
            try:
                if account.mode == "cookie":
                    from .base import parse_cookies
                    injected = parse_cookies(account)
                    apply_raw_cookie(ctx, account)
                    names = ", ".join(c["name"] for c in injected) or "(kosong!)"
                    print(f"   cookie disuntikkan: {names} ({len(injected)} cookie)")
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                if account.mode == "cookie":
                    # Warm-up ONLY for transplanted cookie sessions: land on
                    # the homepage so TikTok can settle/refresh the cookies.
                    # NEVER fatal - TikTok sometimes answers the homepage
                    # with an error status (ERR_HTTP_RESPONSE_CODE_FAILURE,
                    # seen 2026-10-23 00:49); the upload page may still work.
                    try:
                        page.goto("https://www.tiktok.com/",
                                  wait_until="commit", timeout=30_000)
                        page.wait_for_timeout(2500)
                    except Exception:
                        print("   pemanasan homepage dilewati (respons TikTok "
                              "tidak mulus) - lanjut ke halaman upload")
                page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=90_000)
                page.wait_for_timeout(4000)
                if "login" in page.url:
                    raise PublishError(
                        "Sesi TikTok belum login / sudah kedaluwarsa. "
                        "Klik 'Login Browser' di tab Akun untuk akun ini.")
                file_input = page.locator("input[type='file']").first
                file_input.set_input_files(job.video_path, timeout=60_000)
                if job.kind == "image":
                    # TikTok Studio switches to Photo mode for images; the
                    # caption box can take longer to appear.
                    page.wait_for_timeout(5000)
                # Wait for the caption editor + processing.
                editor = page.locator(
                    "div[contenteditable='true'], [data-e2e='caption-input'], "
                    "textarea[placeholder*='caption' i], "
                    "textarea[placeholder*='Describe' i]").first
                editor.wait_for(state="visible", timeout=180_000)
                # TikTok floats a TUXModal over the whole page (real user log
                # 2026-10-22 23:52): the editor EXISTS but every click is
                # intercepted until the modal is closed.
                dismiss_overlays(page, seconds=15)
                try:
                    editor.click(timeout=10_000)
                except Exception:
                    dismiss_overlays(page, seconds=10)
                    editor.click(force=True, timeout=10_000)
                page.keyboard.press("Control+A")
                page.keyboard.type(caption, delay=5)
                if job.cover_path and os.path.isfile(job.cover_path):
                    pass  # Cover selection UI varies; cover is set manually if needed.
                post_btn = page.locator(
                    "button[data-e2e='post_video_button'], button:has-text('Post')").last
                post_btn.wait_for(state="visible", timeout=60_000)
                # Upload processing can take a while; wait until Post is enabled.
                for _ in range(60):
                    if post_btn.is_enabled():
                        break
                    page.wait_for_timeout(5000)
                else:
                    raise PublishError("Upload TikTok tidak selesai diproses (timeout).")
                # TikTok often floats a modal (checks/notices) over the button:
                # clear overlays first, or the click is intercepted forever.
                dismiss_overlays(page, seconds=15)
                try:
                    post_btn.click(timeout=30_000)
                except Exception:
                    dismiss_overlays(page, seconds=15)
                    post_btn.click(timeout=30_000)
                page.wait_for_timeout(3000)
                # A confirmation modal can appear AFTER clicking Post.
                dismiss_overlays(page, seconds=15)
                page.wait_for_timeout(5000)
                label = "Foto" if job.kind == "image" else "Video"
                return ok(account, f"{label} TikTok terbit (cek profil untuk memastikan).",
                          "https://www.tiktok.com/")
            except PublishError as e:
                shot = _screenshot(ctx, logs_dir)
                suffix = f" Screenshot: {shot}" if shot else ""
                raise PublishError(str(e) + suffix)
            finally:
                ctx.close()
    except PublishError as e:
        return fail(account, str(e))
    except Exception as e:  # Playwright errors etc. - report, never swallow.
        return fail(account, friendly_error(e) or f"TikTok browser gagal: {e}")

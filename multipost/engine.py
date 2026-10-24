"""Publish orchestrator.

Rules baked in (from the social-publishing playbook):
- Publish targets SEQUENTIALLY and track each platform separately, so a
  failure on one can never duplicate a post that already succeeded on another.
- NEVER auto-retry a publish. An uncertain result is reported, not repeated.
- dry_run exercises the whole pipeline (caption adaptation, dispatch,
  result bookkeeping) without touching any network or browser.
"""

from __future__ import annotations

import os
import time
from typing import Callable

from .captions import adapt
from .interval import describe as describe_interval
from .interval import next_delay
from .models import Account, Job, PublishResult
from .proxy import playwright_proxy, requests_proxies
from .publishers import (custom_browser, meta_api, meta_browser,
                         tiktok_browser, youtube_browser)
from .store import Store

LogFn = Callable[[str], None]


def _noop(_: str) -> None:
    pass


def resolve_job_for(job: Job, account_id: str) -> Job:
    """Apply a per-account content override (v1.6.0), if any.

    Returns the job as-is when the account has no override, or a copy with
    the override's media/caption swapped in (empty override values fall back
    to the master content, so a caption-only override keeps the master media).
    """
    from dataclasses import replace

    override = (job.overrides or {}).get(account_id) or {}
    media = (override.get("video_path") or "").strip()
    caption = (override.get("caption") or "").strip()
    if not media and not caption:
        return job
    return replace(job,
                   video_path=media or job.video_path,
                   caption=caption or job.caption)


def publish_job(store: Store, job: Job, accounts: list[Account],
                log: LogFn = _noop, dry_run: bool = False,
                on_result=None, settings: dict | None = None) -> list[PublishResult]:
    """on_result(result) fires as EACH platform finishes, so the UI can show
    live per-platform progress instead of one block at the end.

    Between two targets the engine waits the configured posting interval
    (settings['interval_seconds'] + optional jitter) - identical-second
    multi-platform blasts are the easiest spam signal. The wait is logged.
    """
    settings = settings or store.load_settings()
    proxy_cfg = settings.get("proxy") or {}
    meta_api.PROXIES = requests_proxies(proxy_cfg)
    pw_proxy = playwright_proxy(proxy_cfg)
    interval_base = settings.get("interval_seconds", 60)
    interval_random = settings.get("interval_random", True)
    results: list[PublishResult] = []
    by_id = {a.id: a for a in accounts}

    def _emit(result: PublishResult) -> None:
        results.append(result)
        if on_result is not None:
            on_result(result)

    targets = [a for a in (by_id.get(i) for i in job.account_ids) if a is not None]
    log(f"[sistem] Interval antar platform: {describe_interval(interval_base, interval_random)}"
        + (f" via proxy {proxy_cfg.get('type')}://{proxy_cfg.get('host')}:{proxy_cfg.get('port')}"
           if proxy_cfg.get("enabled") and proxy_cfg.get("host") else ""))
    for idx, account_id in enumerate(job.account_ids):
        if idx > 0 and not dry_run:
            delay = next_delay(interval_base, interval_random)
            if delay > 0:
                log(f"[jeda] Menunggu {delay:g} detik sebelum platform berikutnya…")
                time.sleep(delay)
        account = by_id.get(account_id)
        if account is None:
            _emit(PublishResult("?", account_id, "skipped",
                                "Akun tidak ditemukan (sudah dihapus?)."))
            continue
        ajob = resolve_job_for(job, account_id)
        if ajob is not job:
            log(f"[{account.platform}] Konten khusus untuk '{account.label}' "
                f"(media: {os.path.basename(ajob.video_path)})")
        adapted = adapt(account.platform, ajob.caption, ajob.title)
        for w in adapted.warnings:
            log(f"[{account.platform}] {w}")
        if dry_run:
            log(f"[{account.platform}] DRY RUN -> {adapted.text[:80]}...")
            _emit(PublishResult(
                account.platform, account.label, "dry_run",
                f"Simulasi OK. Caption {len(adapted.text)} karakter"
                + (f", judul: {adapted.title}" if adapted.title else "")))
            continue
        log(f"[{account.platform}] Mulai publish ke '{account.label}' ({account.mode})...")
        result = dispatch(store, account, ajob, adapted, pw_proxy)
        log(f"[{account.platform}] {result.status.upper()}: {result.message}")
        _emit(result)
    store.append_history(results)
    return results


def dispatch(store: Store, account: Account, job: Job, adapted,
             pw_proxy: dict | None = None) -> PublishResult:
    profile_dir = store.profile_dir(account.id)
    logs_dir = store.data_dir + "/logs"
    platform, mode = account.platform, account.mode

    if platform == "custom":
        if mode == "api":
            return PublishResult(platform, account.label, "error",
                                 "Platform custom hanya tersedia mode browser.")
        return custom_browser.publish(account, job, adapted.text, profile_dir, logs_dir,
                                      proxy=pw_proxy)
    if platform == "tiktok":
        return tiktok_browser.publish(account, job, adapted.text, profile_dir, logs_dir,
                                      proxy=pw_proxy)
    if platform == "youtube":
        return youtube_browser.publish(account, job, adapted.title, adapted.text,
                                       profile_dir, logs_dir, proxy=pw_proxy)
    # Meta family
    if mode == "api":
        if platform == "instagram":
            return meta_api.publish_instagram(account, job, adapted.text)
        if platform == "threads":
            return meta_api.publish_threads(account, job, adapted.text)
        if platform == "facebook":
            return meta_api.publish_facebook_page(account, job, adapted.text)
    # browser / cookie mode for Meta (experimental fallback)
    return meta_browser.publish(account, job, adapted.text, profile_dir, logs_dir,
                                proxy=pw_proxy)


_ACTIVE_LOGINS: set = set()


def open_login_for(store: Store, account: Account) -> None:
    """Open the platform login page in the account's persistent profile.

    Guarded: a Chromium profile can only be open ONCE - launching it again
    while a login window (or a publish) is using it fails with
    ProcessSingleton lock errors. One login per account at a time.
    """
    profile_dir = store.profile_dir(account.id)
    if profile_dir in _ACTIVE_LOGINS:
        print(f"Login {account.platform} untuk {account.label} sudah terbuka - "
              "selesaikan di jendela itu dulu.")
        return
    _ACTIVE_LOGINS.add(profile_dir)
    try:
        pw_proxy = playwright_proxy(store.load_settings().get("proxy"))
        if account.platform == "custom":
            custom_browser.open_login(account, profile_dir, proxy=pw_proxy)
        elif account.platform == "tiktok":
            tiktok_browser.open_login(profile_dir, proxy=pw_proxy)
        elif account.platform == "youtube":
            youtube_browser.open_login(profile_dir, proxy=pw_proxy)
        else:
            meta_browser.open_login(account.platform, profile_dir, proxy=pw_proxy)
    finally:
        _ACTIVE_LOGINS.discard(profile_dir)

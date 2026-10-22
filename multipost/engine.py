"""Publish orchestrator.

Rules baked in (from the social-publishing playbook):
- Publish targets SEQUENTIALLY and track each platform separately, so a
  failure on one can never duplicate a post that already succeeded on another.
- NEVER auto-retry a publish. An uncertain result is reported, not repeated.
- dry_run exercises the whole pipeline (caption adaptation, dispatch,
  result bookkeeping) without touching any network or browser.
"""

from __future__ import annotations

from typing import Callable

from .captions import adapt
from .models import Account, Job, PublishResult
from .publishers import meta_api, meta_browser, tiktok_browser, youtube_browser
from .store import Store

LogFn = Callable[[str], None]


def _noop(_: str) -> None:
    pass


def publish_job(store: Store, job: Job, accounts: list[Account],
                log: LogFn = _noop, dry_run: bool = False,
                on_result=None) -> list[PublishResult]:
    """on_result(result) fires as EACH platform finishes, so the UI can show
    live per-platform progress instead of one block at the end."""
    results: list[PublishResult] = []
    by_id = {a.id: a for a in accounts}

    def _emit(result: PublishResult) -> None:
        results.append(result)
        if on_result is not None:
            on_result(result)

    for account_id in job.account_ids:
        account = by_id.get(account_id)
        if account is None:
            _emit(PublishResult("?", account_id, "skipped",
                                "Akun tidak ditemukan (sudah dihapus?)."))
            continue
        adapted = adapt(account.platform, job.caption, job.title)
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
        result = dispatch(store, account, job, adapted)
        log(f"[{account.platform}] {result.status.upper()}: {result.message}")
        _emit(result)
    store.append_history(results)
    return results


def dispatch(store: Store, account: Account, job: Job, adapted) -> PublishResult:
    profile_dir = store.profile_dir(account.id)
    logs_dir = store.data_dir + "/logs"
    platform, mode = account.platform, account.mode

    if platform == "tiktok":
        return tiktok_browser.publish(account, job, adapted.text, profile_dir, logs_dir)
    if platform == "youtube":
        return youtube_browser.publish(account, job, adapted.title, adapted.text,
                                       profile_dir, logs_dir)
    # Meta family
    if mode == "api":
        if platform == "instagram":
            return meta_api.publish_instagram(account, job, adapted.text)
        if platform == "threads":
            return meta_api.publish_threads(account, job, adapted.text)
        if platform == "facebook":
            return meta_api.publish_facebook_page(account, job, adapted.text)
    # browser / cookie mode for Meta (experimental fallback)
    return meta_browser.publish(account, job, adapted.text, profile_dir, logs_dir)


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
        if account.platform == "tiktok":
            tiktok_browser.open_login(profile_dir)
        elif account.platform == "youtube":
            youtube_browser.open_login(profile_dir)
        else:
            meta_browser.open_login(account.platform, profile_dir)
    finally:
        _ACTIVE_LOGINS.discard(profile_dir)

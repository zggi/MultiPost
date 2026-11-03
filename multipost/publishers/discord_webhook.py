"""Discord publisher (v1.8.0): posts to a server channel through that
channel's webhook URL - no bot, no OAuth, no browser.

Setup (once, by the user, in Discord): Server Settings -> Integrations ->
Webhooks -> New Webhook -> pick the channel -> Copy Webhook URL -> paste
it into MultiPost's Akun tab (platform "discord"). One webhook = one
channel, so one account row per channel. The URL is a secret: anyone who
has it can post to that channel, so it is stored DPAPI-encrypted like
every other account secret and must never be shared.

Honest limits:
- Message content max 2000 characters (caption is truncated by adapt()).
- Webhook file uploads are capped at 25 MB on standard servers (boosted
  servers allow more, but we cannot detect the boost level, so >25 MB
  fails with a clear message instead of a cryptic Discord error).
"""

from __future__ import annotations

import os

# Set by engine.publish_job from the global proxy settings ({} = direct).
PROXIES: dict = {}

import requests

from ..models import Account, Job, PublishResult
from .base import PublishError, fail, ok, require_file

MAX_FILE_BYTES = 25 * 1024 * 1024
WEBHOOK_PREFIXES = ("https://discord.com/api/webhooks/",
                    "https://discordapp.com/api/webhooks/")


def _webhook_url(account: Account) -> str:
    url = (account.secret or "").strip()
    if not url.startswith(WEBHOOK_PREFIXES):
        raise PublishError(
            "URL webhook Discord tidak valid. Salin dari Server Settings -> "
            "Integrations -> Webhooks (harus diawali "
            "https://discord.com/api/webhooks/).")
    return url


def publish(account: Account, job: Job, caption: str) -> PublishResult:
    try:
        url = _webhook_url(account)
        require_file(job.video_path)
        size = os.path.getsize(job.video_path)
        if size > MAX_FILE_BYTES:
            raise PublishError(
                f"File {size / 1024 / 1024:.1f} MB melebihi batas upload "
                "webhook Discord standar (25 MB). Kecilkan/kompres file, "
                "atau pakai server ter-boost.")
        with open(job.video_path, "rb") as fh:
            resp = requests.post(
                url,
                data={"content": (caption or "")[:2000]},
                files={"file": (os.path.basename(job.video_path), fh)},
                proxies=PROXIES, timeout=300)
        if resp.status_code in (200, 204):
            return ok(account, "Terkirim ke channel Discord via webhook.")
        try:
            detail = resp.json().get("message", resp.text[:300])
        except ValueError:
            detail = resp.text[:300]
        raise PublishError(f"Discord menolak ({resp.status_code}): {detail}")
    except Exception as e:  # noqa: BLE001 - surfaced to the user as a result
        from .base import friendly_error
        return fail(account, friendly_error(e) or str(e))

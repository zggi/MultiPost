"""Meta Graph API publisher: Instagram Reels, Threads, Facebook Page.

Honest platform limits (documented in README):
- Instagram & Threads API publishing needs a PUBLIC video URL - the Graph
  API does not accept a local file upload. Without `media_url` we fail with a
  clear message instead of pretending.
- Facebook Page video DOES accept a local file upload (multipart `source`).
- Instagram account must be Business/Creator; token needs
  instagram_content_publish / threads_content_publish / pages_manage_posts.
"""

from __future__ import annotations

import os
import time

import requests

from ..models import Account, Job, PublishResult
from .base import PublishError, fail, ok, require_file

GRAPH = "https://graph.facebook.com/v21.0"
THREADS_GRAPH = "https://graph.threads.net/v1.0"


def _check(resp: requests.Response, what: str) -> dict:
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400 or "error" in data:
        msg = (data.get("error") or {}).get("message", resp.text[:300])
        raise PublishError(f"{what} gagal: {msg}")
    return data


def _require_token(account: Account) -> str:
    if not account.secret:
        raise PublishError(
            "Token API kosong. Isi Access Token di tab Akun (lihat PANDUAN-AKUN.md).")
    return account.secret


def _require_media_url(job: Job, platform: str) -> str:
    if not job.media_url:
        raise PublishError(
            f"Mode API {platform} butuh URL publik video (API Meta tidak menerima "
            "upload file lokal). Isi kolom 'URL publik video', atau pakai mode Browser "
            "untuk akun ini.")
    return job.media_url


def publish_instagram(account: Account, job: Job, caption: str) -> PublishResult:
    try:
        token = _require_token(account)
        ig_id = account.extra.get("ig_user_id")
        if not ig_id:
            raise PublishError("IG User ID kosong. Isi di tab Akun (PANDUAN-AKUN.md).")
        media_url = _require_media_url(job, "Instagram")
        if job.kind == "image":
            payload = {"image_url": media_url, "caption": caption,
                       "access_token": token}
        else:
            payload = {"media_type": "REELS", "video_url": media_url,
                       "caption": caption, "access_token": token}
        r = requests.post(f"{GRAPH}/{ig_id}/media", data=payload, timeout=60)
        container = _check(r, "Buat container Instagram").get("id")
        # Poll container until FINISHED (max ~5 min).
        for _ in range(30):
            time.sleep(10)
            r = requests.get(f"{GRAPH}/{container}", params={
                "fields": "status_code", "access_token": token}, timeout=30)
            status = _check(r, "Cek status container").get("status_code")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise PublishError("Instagram gagal memproses video (container ERROR).")
        else:
            raise PublishError("Timeout menunggu Instagram memproses video.")
        r = requests.post(f"{GRAPH}/{ig_id}/media_publish", data={
            "creation_id": container, "access_token": token}, timeout=60)
        media_id = _check(r, "Publish Instagram").get("id")
        kind_label = "Foto" if job.kind == "image" else "Reels"
        return ok(account, f"{kind_label} Instagram terbit (media {media_id}).",
                  f"https://www.instagram.com/p/{media_id}/")
    except PublishError as e:
        return fail(account, str(e))
    except requests.RequestException as e:
        return fail(account, f"Koneksi ke Meta API gagal: {e}")


def publish_threads(account: Account, job: Job, caption: str) -> PublishResult:
    try:
        token = _require_token(account)
        user_id = account.extra.get("threads_user_id")
        if not user_id:
            raise PublishError("Threads User ID kosong. Isi di tab Akun (PANDUAN-AKUN.md).")
        media_url = _require_media_url(job, "Threads")
        if job.kind == "image":
            payload = {"media_type": "IMAGE", "image_url": media_url,
                       "text": caption, "access_token": token}
        else:
            payload = {"media_type": "VIDEO", "video_url": media_url,
                       "text": caption, "access_token": token}
        r = requests.post(f"{THREADS_GRAPH}/{user_id}/threads", data=payload, timeout=60)
        container = _check(r, "Buat container Threads").get("id")
        for _ in range(30):
            time.sleep(10)
            r = requests.get(f"{THREADS_GRAPH}/{container}", params={
                "fields": "status", "access_token": token}, timeout=30)
            status = _check(r, "Cek status Threads").get("status")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise PublishError("Threads gagal memproses video (container ERROR).")
        else:
            raise PublishError("Timeout menunggu Threads memproses video.")
        r = requests.post(f"{THREADS_GRAPH}/{user_id}/threads_publish", data={
            "creation_id": container, "access_token": token}, timeout=60)
        post_id = _check(r, "Publish Threads").get("id")
        return ok(account, f"Post Threads terbit (id {post_id}).")
    except PublishError as e:
        return fail(account, str(e))
    except requests.RequestException as e:
        return fail(account, f"Koneksi ke Threads API gagal: {e}")


def publish_facebook_page(account: Account, job: Job, caption: str) -> PublishResult:
    try:
        token = _require_token(account)
        page_id = account.extra.get("page_id")
        if not page_id:
            raise PublishError("Page ID kosong. Isi di tab Akun (PANDUAN-AKUN.md).")
        require_file(job.video_path)
        if job.kind == "image":
            with open(job.video_path, "rb") as fh:
                r = requests.post(
                    f"{GRAPH}/{page_id}/photos",
                    data={"caption": caption, "access_token": token},
                    files={"source": fh}, timeout=300)
            photo = _check(r, "Upload foto Facebook Page")
            photo_id = photo.get("id") or photo.get("post_id")
            return ok(account, f"Foto Facebook Page terbit (id {photo_id}).",
                      f"https://www.facebook.com/photo/?fbid={photo_id}")
        with open(job.video_path, "rb") as fh:
            r = requests.post(
                f"{GRAPH}/{page_id}/videos",
                data={"description": caption, "access_token": token,
                      "title": os.path.basename(job.video_path)},
                files={"source": fh}, timeout=600)
        video_id = _check(r, "Upload video Facebook Page").get("id")
        return ok(account, f"Video Facebook Page terbit (id {video_id}).",
                  f"https://www.facebook.com/watch/?v={video_id}")
    except PublishError as e:
        return fail(account, str(e))
    except requests.RequestException as e:
        return fail(account, f"Koneksi ke Meta API gagal: {e}")

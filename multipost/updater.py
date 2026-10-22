"""In-app auto-update, KasirMan-style: poll the public GitHub repo's latest
release, compare versions, download MultiPost-Setup.exe, run it, quit.

Why the repo must be PUBLIC: the app checks anonymously (no token may ever
ship inside the app). The repo contains source code only - accounts, tokens
and cookies live exclusively in data/ on the user's PC, never in the repo.
"""

from __future__ import annotations

import os
import subprocess
import tempfile

import requests

REPO = "zggi/MultiPost"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
SETUP_ASSET = "MultiPost-Setup.exe"


def parse_version(text: str) -> tuple:
    """'v1.4.0' / '1.4.0' -> (1, 4, 0). Non-numeric parts become 0."""
    parts = []
    for chunk in str(text).lstrip("vV").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(current: str, latest: str) -> bool:
    return parse_version(latest) > parse_version(current)


def pick_setup_asset(release: dict) -> dict | None:
    for asset in release.get("assets", []):
        if asset.get("name") == SETUP_ASSET:
            return {"name": asset["name"], "size": asset.get("size", 0),
                    "id": asset.get("id"),
                    "url": asset.get("browser_download_url", "")}
    return None


def check_latest(current_version: str, timeout: int = 12) -> dict | None:
    """Return update info dict if a newer release with a Setup asset exists,
    else None. Any network/parse failure returns None - update checks are
    silent by design (same rule as the KasirMan updater)."""
    try:
        resp = requests.get(LATEST_URL, timeout=timeout, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MultiPost-Updater"})
        if resp.status_code != 200:
            return None
        release = resp.json()
        tag = release.get("tag_name", "")
        if not tag or not is_newer(current_version, tag):
            return None
        asset = pick_setup_asset(release)
        if not asset:
            return None
        return {"version": tag.lstrip("vV"), "tag": tag,
                "notes": (release.get("body") or "")[:1200], **asset}
    except Exception:
        return None


def download_sources(info: dict) -> list:
    """Ordered download routes for the Setup asset.

    Route 1 goes through api.github.com (the same host the version CHECK
    uses - proven reachable even when github.com's download redirect stalls
    on some ISPs, which froze the v1.4.2 progress bar at 0%). Route 2 is the
    plain browser_download_url.
    """
    sources = []
    if info.get("id"):
        sources.append((
            f"https://api.github.com/repos/{REPO}/releases/assets/{info['id']}",
            {"Accept": "application/octet-stream",
             "User-Agent": "MultiPost-Updater"}))
    if info.get("url"):
        sources.append((info["url"], {"User-Agent": "MultiPost-Updater"}))
    return sources


def download_setup(info: dict, progress=None) -> str:
    """Stream the Setup.exe to %TEMP%, trying each route in order.

    progress(done_bytes, total_bytes) fires per chunk so the UI can show a
    live MB counter - a stall is visible immediately instead of a frozen %.
    Timeouts are (connect 10s, read 25s per chunk): a dead route fails fast
    and the next route is tried, instead of hanging forever.
    """
    dest = os.path.join(tempfile.gettempdir(), f"MultiPost-Setup-{info['tag']}.exe")
    errors = []
    for url, headers in download_sources(info):
        try:
            with requests.get(url, stream=True, timeout=(10, 25),
                              headers=headers) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length")
                            or info.get("size") or 0)
                done = 0
                with open(dest, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=262144):
                        if not chunk:
                            continue
                        fh.write(chunk)
                        done += len(chunk)
                        if progress:
                            progress(done, total)
            if os.path.getsize(dest) < 1_000_000:
                raise RuntimeError("file terlalu kecil - unduhan tidak utuh")
            return dest
        except Exception as e:  # try the next route; report if all fail
            errors.append(f"{url.split('/')[2]}: {e}")
    raise RuntimeError("Semua jalur unduh gagal - " + " | ".join(errors))


def launch_installer(path: str) -> None:
    subprocess.Popen([path], close_fds=True)

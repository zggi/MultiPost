"""Per-platform caption adaptation.

One master caption in, one platform-correct text out. Truncation is always
reported as a warning so the UI can show it BEFORE anything is published -
nothing is silently cut.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LIMITS = {
    "instagram": 2200,
    "threads": 500,
    "facebook": 5000,   # practical composer limit we target for Page posts
    "tiktok": 2200,
    "youtube_desc": 5000,
    "youtube_title": 100,
}


@dataclass
class Adapted:
    text: str  # caption / description for the platform
    title: str = ""  # YouTube only
    warnings: list = field(default_factory=list)


def _truncate(text: str, limit: int, platform: str, warnings: list) -> str:
    if len(text) <= limit:
        return text
    warnings.append(
        f"{platform}: teks {len(text)} karakter melebihi batas {limit}, dipotong."
    )
    cut = text[: limit - 1].rstrip()
    # Prefer cutting at the last space so we do not slice a word / hashtag.
    if " " in cut:
        cut = cut[: cut.rfind(" ")].rstrip()
    return cut + "…"


def adapt(platform: str, caption: str, title: str = "") -> Adapted:
    caption = (caption or "").strip()
    warnings: list = []
    if platform == "custom":
        # A user-defined site has no known limit - pass the caption through.
        return Adapted(text=caption, warnings=warnings)
    if platform == "youtube":
        yt_title = (title or "").strip() or (caption.splitlines()[0] if caption else "")
        yt_title = _truncate(yt_title, LIMITS["youtube_title"], "youtube (judul)", warnings)
        desc = _truncate(caption, LIMITS["youtube_desc"], "youtube (deskripsi)", warnings)
        return Adapted(text=desc, title=yt_title, warnings=warnings)
    limit = LIMITS.get(platform, 2200)
    return Adapted(text=_truncate(caption, limit, platform, warnings), warnings=warnings)

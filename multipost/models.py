"""Data models for MultiPost. Plain dataclasses, JSON-serialisable."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field

MODES = ("api", "browser", "cookie")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Account:
    """One social account. `secret` is NEVER stored in plain text on disk:
    the store encrypts it (Windows DPAPI) before writing accounts.json."""

    platform: str  # instagram | threads | facebook | tiktok | youtube
    label: str  # display name chosen by the user, e.g. "KasirMan IG"
    mode: str = "browser"  # api | browser | cookie
    secret: str = ""  # API access token OR raw cookie value (cookie mode)
    extra: dict = field(default_factory=dict)
    # extra keys by platform/mode:
    #   api/instagram : {"ig_user_id": "..."}
    #   api/threads   : {"threads_user_id": "..."}
    #   api/facebook  : {"page_id": "..."}
    #   cookie/*      : {"cookie_name": "sessionid", "cookie_domain": ".tiktok.com"}
    id: str = field(default_factory=_new_id)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Account":
        return cls(
            platform=d["platform"],
            label=d.get("label", d["platform"]),
            mode=d.get("mode", "browser"),
            secret=d.get("secret", ""),
            extra=d.get("extra", {}) or {},
            id=d.get("id") or _new_id(),
        )


@dataclass
class PublishResult:
    platform: str
    account_label: str
    status: str  # success | failed | skipped | dry_run
    message: str = ""
    url: str = ""
    at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Job:
    """One compose submission: one video + one master caption, many targets."""

    video_path: str
    caption: str
    title: str = ""  # used by YouTube; falls back to first caption line
    media_url: str = ""  # public video URL, REQUIRED by Meta API mode (IG/Threads)
    cover_path: str = ""
    account_ids: list = field(default_factory=list)
    scheduled_at: float = 0.0  # 0 = publish now
    id: str = field(default_factory=_new_id)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        return cls(
            video_path=d["video_path"],
            caption=d.get("caption", ""),
            title=d.get("title", ""),
            media_url=d.get("media_url", ""),
            cover_path=d.get("cover_path", ""),
            account_ids=d.get("account_ids", []),
            scheduled_at=d.get("scheduled_at", 0.0),
            id=d.get("id") or _new_id(),
            created_at=d.get("created_at", time.time()),
        )

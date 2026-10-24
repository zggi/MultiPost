import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost.engine import resolve_job_for  # noqa: E402
from multipost.models import Job  # noqa: E402


def _job():
    return Job(video_path="/master.mp4", caption="master caption",
               account_ids=["a1", "a2"],
               overrides={
                   "a1": {"video_path": "/khusus.mp4", "caption": "caption khusus"},
                   "a2": {"video_path": "", "caption": "hanya caption beda"},
               })


def test_no_override_returns_same_job():
    job = _job()
    assert resolve_job_for(job, "unknown") is job


def test_full_override_replaces_both():
    out = resolve_job_for(_job(), "a1")
    assert out.video_path == "/khusus.mp4"
    assert out.caption == "caption khusus"
    assert out.account_ids == ["a1", "a2"]  # other fields untouched


def test_caption_only_override_keeps_master_media():
    out = resolve_job_for(_job(), "a2")
    assert out.video_path == "/master.mp4"
    assert out.caption == "hanya caption beda"


def test_job_roundtrip_keeps_overrides():
    job = _job()
    restored = Job.from_dict(job.to_dict())
    assert restored.overrides == job.overrides
    assert resolve_job_for(restored, "a1").caption == "caption khusus"

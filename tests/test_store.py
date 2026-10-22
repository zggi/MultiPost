import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost.models import Account, Job  # noqa: E402
from multipost.store import Store  # noqa: E402


def test_secret_is_encrypted_on_disk_and_roundtrips(tmp_path):
    store = Store(str(tmp_path))
    store.upsert_account(Account(platform="tiktok", label="Tes", mode="cookie",
                                 secret="SECRET-VALUE-123"))
    raw = open(store.accounts_file, encoding="utf-8").read()
    assert "SECRET-VALUE-123" not in raw, "secret must never be plain on disk"
    loaded = store.load_accounts()
    assert loaded[0].secret == "SECRET-VALUE-123"
    assert loaded[0].platform == "tiktok"


def test_job_schedule_roundtrip(tmp_path):
    store = Store(str(tmp_path))
    store.add_job(Job(video_path="v.mp4", caption="c", account_ids=["a1"],
                      scheduled_at=9999999999))
    jobs = store.load_jobs()
    assert len(jobs) == 1 and jobs[0].scheduled_at == 9999999999
    store.remove_job(jobs[0].id)
    assert store.load_jobs() == []

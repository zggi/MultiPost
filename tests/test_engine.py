import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost.engine import publish_job  # noqa: E402
from multipost.models import Account, Job  # noqa: E402
from multipost.store import Store  # noqa: E402

PLATFORMS = ["instagram", "threads", "facebook", "tiktok", "youtube"]


def test_dry_run_covers_all_five_platforms(tmp_path):
    store = Store(str(tmp_path))
    accounts = [Account(platform=p, label=f"Tes {p}", mode="browser")
                for p in PLATFORMS]
    job = Job(video_path="v.mp4", caption="Satu caption untuk semua",
              account_ids=[a.id for a in accounts])
    results = publish_job(store, job, accounts, dry_run=True)
    assert [r.platform for r in results] == PLATFORMS
    assert all(r.status == "dry_run" for r in results)
    assert len(store.load_history()) == 5


def test_missing_account_is_skipped_not_crash(tmp_path):
    store = Store(str(tmp_path))
    job = Job(video_path="v.mp4", caption="c", account_ids=["tidak-ada"])
    results = publish_job(store, job, [], dry_run=True)
    assert results[0].status == "skipped"

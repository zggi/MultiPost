"""Headless helpers - used for smoke tests and debugging without the UI."""

from __future__ import annotations

import argparse

from .engine import publish_job
from .models import Job
from .store import Store


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="multipost")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("accounts", help="list configured accounts")
    p = sub.add_parser("dry-run", help="simulate a publish for all accounts")
    p.add_argument("--video", default="contoh.mp4")
    p.add_argument("--caption", default="Tes MultiPost #uji")
    args = parser.parse_args(argv)

    store = Store()
    accounts = store.load_accounts()
    if args.cmd == "accounts":
        if not accounts:
            print("Belum ada akun. Tambahkan lewat UI (tab Akun).")
        for a in accounts:
            print(f"- [{a.platform}] {a.label} (mode: {a.mode})")
        return 0
    if args.cmd == "dry-run":
        if not accounts:
            print("Tidak ada akun untuk dry-run.")
            return 1
        job = Job(video_path=args.video, caption=args.caption,
                  account_ids=[a.id for a in accounts])
        results = publish_job(store, job, accounts,
                              log=lambda m: print(m), dry_run=True)
        for r in results:
            print(f"{r.platform}: {r.status} - {r.message}")
        return 0
    return 2

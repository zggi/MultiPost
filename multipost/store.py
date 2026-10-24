"""Local storage: accounts (secrets encrypted), pending jobs, history.

Everything lives under <app_dir>/data/ on the USER'S OWN PC. Nothing is sent
anywhere by this module.
"""

from __future__ import annotations

import json
import os

from .crypto_store import decrypt_str, encrypt_str
from .models import Account, Job, PublishResult
from .proxy import DEFAULTS as PROXY_DEFAULTS


def default_data_dir() -> str:
    # Next to the executable / project, so the user's layout stays predictable:
    # C:\BOT\MultiPost\data\ (source mode) or next to MultiPost.exe (frozen).
    import sys
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data")


class Store:
    def __init__(self, data_dir: str | None = None):
        self.data_dir = data_dir or default_data_dir()
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "profiles"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "logs"), exist_ok=True)
        self.accounts_file = os.path.join(self.data_dir, "accounts.json")
        self.jobs_file = os.path.join(self.data_dir, "jobs.json")
        self.history_file = os.path.join(self.data_dir, "history.json")
        self.settings_file = os.path.join(self.data_dir, "settings.json")

    # ---- global settings (interval + proxy) ------------------------------
    def load_settings(self) -> dict:
        settings = {"interval_seconds": 60, "interval_random": True,
                    "proxy": dict(PROXY_DEFAULTS)}
        if os.path.exists(self.settings_file):
            try:
                saved = json.loads(open(self.settings_file, encoding="utf-8").read() or "{}")
            except Exception:
                saved = {}
            settings.update({k: v for k, v in saved.items() if k in settings})
            proxy = dict(PROXY_DEFAULTS)
            proxy.update(saved.get("proxy", {}) or {})
            proxy["password"] = decrypt_str(proxy.get("password_enc", ""),
                                            self.data_dir)
            proxy.pop("password_enc", None)
            settings["proxy"] = proxy
        return settings

    def save_settings(self, settings: dict) -> None:
        proxy = dict(PROXY_DEFAULTS)
        proxy.update((settings.get("proxy") or {}))
        proxy["password_enc"] = encrypt_str(proxy.pop("password", ""),
                                            self.data_dir)
        out = {"interval_seconds": settings.get("interval_seconds", 60),
               "interval_random": settings.get("interval_random", True),
               "proxy": proxy}
        self._write(self.settings_file, out)

    # ---- accounts -------------------------------------------------------
    def load_accounts(self) -> list[Account]:
        if not os.path.exists(self.accounts_file):
            return []
        rows = json.loads(open(self.accounts_file, encoding="utf-8").read() or "[]")
        accounts = []
        for row in rows:
            row = dict(row)
            row["secret"] = decrypt_str(row.get("secret_enc", ""), self.data_dir)
            row.pop("secret_enc", None)
            accounts.append(Account.from_dict(row))
        return accounts

    def save_accounts(self, accounts: list[Account]) -> None:
        rows = []
        for acc in accounts:
            d = acc.to_dict()
            d["secret_enc"] = encrypt_str(d.pop("secret", ""), self.data_dir)
            rows.append(d)
        self._write(self.accounts_file, rows)

    def upsert_account(self, acc: Account) -> None:
        accounts = self.load_accounts()
        for i, existing in enumerate(accounts):
            if existing.id == acc.id:
                accounts[i] = acc
                break
        else:
            accounts.append(acc)
        self.save_accounts(accounts)

    def delete_account(self, account_id: str) -> None:
        self.save_accounts([a for a in self.load_accounts() if a.id != account_id])

    def profile_dir(self, account_id: str) -> str:
        path = os.path.join(self.data_dir, "profiles", account_id)
        os.makedirs(path, exist_ok=True)
        return path

    # ---- scheduled jobs ---------------------------------------------------
    def load_jobs(self) -> list[Job]:
        if not os.path.exists(self.jobs_file):
            return []
        rows = json.loads(open(self.jobs_file, encoding="utf-8").read() or "[]")
        return [Job.from_dict(r) for r in rows]

    def save_jobs(self, jobs: list[Job]) -> None:
        self._write(self.jobs_file, [j.to_dict() for j in jobs])

    def add_job(self, job: Job) -> None:
        jobs = self.load_jobs()
        jobs.append(job)
        self.save_jobs(jobs)

    def remove_job(self, job_id: str) -> None:
        self.save_jobs([j for j in self.load_jobs() if j.id != job_id])

    # ---- history ----------------------------------------------------------
    def append_history(self, results: list[PublishResult]) -> None:
        rows = []
        if os.path.exists(self.history_file):
            rows = json.loads(open(self.history_file, encoding="utf-8").read() or "[]")
        rows.extend(r.to_dict() for r in results)
        self._write(self.history_file, rows[-500:])  # keep last 500 entries

    def load_history(self) -> list[dict]:
        if not os.path.exists(self.history_file):
            return []
        return json.loads(open(self.history_file, encoding="utf-8").read() or "[]")

    @staticmethod
    def _write(path: str, rows) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

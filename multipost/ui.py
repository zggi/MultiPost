"""PySide6 desktop UI: Compose | Akun | Jadwal & Riwayat.

Design rules honoured here:
- The Publish button shows an exact summary (accounts, adapted captions)
  and asks for ONE confirmation before anything is sent - that confirmation
  covers exactly what is shown, nothing else.
- Browser publishers run in a worker thread so the UI never freezes; a
  publish in flight cannot be started twice.
"""

from __future__ import annotations

import os
import time

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateTimeEdit, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from . import PLATFORM_LABELS, PLATFORMS
from .captions import adapt
from .engine import open_login_for, publish_job
from .models import Account, Job
from .store import Store


class PublishWorker(QThread):
    log = Signal(str)
    done = Signal(list)

    def __init__(self, store: Store, job: Job, accounts: list[Account]):
        super().__init__()
        self.store, self.job, self.accounts = store, job, accounts

    def run(self):
        results = publish_job(self.store, self.job, self.accounts,
                              log=self.log.emit)
        self.done.emit([r.to_dict() for r in results])


class LoginWorker(QThread):
    done = Signal(str)

    def __init__(self, store: Store, account: Account):
        super().__init__()
        self.store, self.account = store, account

    def run(self):
        try:
            open_login_for(self.store, self.account)
            self.done.emit(f"Login selesai: {self.account.label}. Sesi tersimpan.")
        except Exception as e:  # surface, never swallow
            self.done.emit(f"Login gagal: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MultiPost v1 Hybrid - 1 Video, 5 Platform")
        self.resize(980, 700)
        self.store = Store()
        self.worker: PublishWorker | None = None
        self.login_worker: LoginWorker | None = None
        self.account_checks: dict[str, QCheckBox] = {}

        tabs = QTabWidget()
        tabs.addTab(self._compose_tab(), "📤 Posting")
        tabs.addTab(self._accounts_tab(), "🔑 Akun")
        tabs.addTab(self._history_tab(), "🕘 Jadwal & Riwayat")
        self.setCentralWidget(tabs)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_schedule)
        self.timer.start(30_000)
        self._refresh_accounts()
        self._refresh_history()

    # ---------------------------------------------------------------- compose
    def _compose_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self.video_edit = QLineEdit()
        self.video_edit.setPlaceholderText("Pilih file video vertikal (MP4, 9:16)...")
        btn = QPushButton("Pilih Video...")
        btn.clicked.connect(self._pick_video)
        row.addWidget(self.video_edit)
        row.addWidget(btn)
        lay.addLayout(row)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Judul YouTube (opsional, kosong = baris pertama caption)")
        lay.addWidget(self.title_edit)

        self.media_url_edit = QLineEdit()
        self.media_url_edit.setPlaceholderText(
            "URL publik video (WAJIB hanya untuk akun Meta mode API: IG/Threads)")
        lay.addWidget(self.media_url_edit)

        lay.addWidget(QLabel("Caption (satu untuk semua, otomatis disesuaikan per platform):"))
        self.caption_edit = QPlainTextEdit()
        self.caption_edit.setPlaceholderText(
            "Tulis caption di sini... Ingat strategi soft selling: jangan pitch langsung, "
            "CTA follow/komen/tag teman.")
        self.caption_edit.setMaximumHeight(130)
        lay.addWidget(self.caption_edit)

        lay.addWidget(QLabel("Posting ke akun:"))
        self.accounts_box = QVBoxLayout()
        lay.addLayout(self.accounts_box)

        sched = QHBoxLayout()
        self.schedule_check = QCheckBox("Jadwalkan pada:")
        self.schedule_edit = QDateTimeEdit()
        self.schedule_edit.setCalendarPopup(True)
        from PySide6.QtCore import QDateTime
        self.schedule_edit.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        sched.addWidget(self.schedule_check)
        sched.addWidget(self.schedule_edit)
        sched.addStretch()
        lay.addLayout(sched)

        self.publish_btn = QPushButton("🚀 POSTING SEKARANG")
        self.publish_btn.setMinimumHeight(42)
        self.publish_btn.clicked.connect(self._publish_clicked)
        lay.addWidget(self.publish_btn)

        lay.addWidget(QLabel("Log:"))
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        lay.addWidget(self.log_edit)
        return w

    def _pick_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih video", "", "Video (*.mp4 *.mov *.webm)")
        if path:
            self.video_edit.setText(path)

    def _publish_clicked(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Sabar", "Publish sebelumnya masih berjalan.")
            return
        video = self.video_edit.text().strip()
        if not os.path.isfile(video):
            QMessageBox.warning(self, "Video", "Pilih file video yang ada dulu.")
            return
        selected = [aid for aid, cb in self.account_checks.items() if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "Akun", "Centang minimal 1 akun tujuan.")
            return
        accounts = self.store.load_accounts()
        by_id = {a.id: a for a in accounts}
        lines = []
        for aid in selected:
            acc = by_id[aid]
            ad = adapt(acc.platform, self.caption_edit.toPlainText(),
                       self.title_edit.text())
            lines.append(f"• {PLATFORM_LABELS[acc.platform]} — {acc.label} ({acc.mode}): "
                         f"{len(ad.text)} karakter")
            for warn in ad.warnings:
                lines.append(f"    ⚠️ {warn}")
        scheduled = self.schedule_check.isChecked()
        when = "dijadwalkan" if scheduled else "SEKARANG"
        msg = (f"Posting {when}?\n\nVideo: {os.path.basename(video)}\n"
               + "\n".join(lines)
               + "\n\nKlik OK untuk menerbitkan persis versi ini.")
        if QMessageBox.question(self, "Konfirmasi Publish", msg) != QMessageBox.Yes:
            return
        job = Job(video_path=video,
                  caption=self.caption_edit.toPlainText(),
                  title=self.title_edit.text(),
                  media_url=self.media_url_edit.text().strip(),
                  account_ids=selected)
        if scheduled:
            job.scheduled_at = self.schedule_edit.dateTime().toSecsSinceEpoch()
            self.store.add_job(job)
            self._log(f"Job dijadwalkan: {time.strftime('%d/%m %H:%M', time.localtime(job.scheduled_at))}")
            self._refresh_history()
            return
        self._run_job(job)

    def _run_job(self, job: Job):
        accounts = self.store.load_accounts()
        self.publish_btn.setEnabled(False)
        self.worker = PublishWorker(self.store, job, accounts)
        self.worker.log.connect(self._log)
        self.worker.done.connect(self._publish_done)
        self.worker.start()

    def _publish_done(self, results: list):
        self.publish_btn.setEnabled(True)
        for r in results:
            self._log(f"HASIL {r['platform']} ({r['account_label']}): "
                      f"{r['status']} - {r['message']} {r.get('url', '')}")
        self._refresh_history()

    def _check_schedule(self):
        now = time.time()
        for job in self.store.load_jobs():
            if job.scheduled_at and job.scheduled_at <= now:
                self.store.remove_job(job.id)
                self._log("Menjalankan job terjadwal...")
                self._run_job(job)

    def _log(self, text: str):
        self.log_edit.appendPlainText(
            f"[{time.strftime('%H:%M:%S')}] {text}")

    # ---------------------------------------------------------------- accounts
    def _accounts_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        split = QSplitter()
        self.accounts_table = QTableWidget(0, 4)
        self.accounts_table.setHorizontalHeaderLabels(
            ["Platform", "Label", "Mode", "ID/Info"])
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(self.accounts_table)
        del_btn = QPushButton("Hapus Akun Terpilih")
        del_btn.clicked.connect(self._delete_account)
        ll.addWidget(del_btn)
        login_btn = QPushButton("🌐 Login Browser (untuk akun terpilih)")
        login_btn.clicked.connect(self._login_selected)
        ll.addWidget(login_btn)
        split.addWidget(left)

        form_w = QWidget()
        form = QFormLayout(form_w)
        self.acc_platform = QComboBox()
        self.acc_platform.addItems(list(PLATFORMS))
        self.acc_label = QLineEdit()
        self.acc_mode = QComboBox()
        self.acc_mode.addItems(["browser", "api", "cookie"])
        self.acc_secret = QPlainTextEdit()
        self.acc_secret.setMaximumHeight(64)
        self.acc_secret.setPlaceholderText(
            "API: Access Token | Cookie: nilai sessionid, atau paste JSON export Cookie-Editor utuh")
        self.acc_extra_id = QLineEdit()
        self.acc_extra_id.setPlaceholderText("IG User ID / Threads User ID / Page ID (mode API)")
        self.acc_cookie_name = QLineEdit("sessionid")
        form.addRow("Platform:", self.acc_platform)
        form.addRow("Label akun:", self.acc_label)
        form.addRow("Mode:", self.acc_mode)
        form.addRow("Token / Cookie:", self.acc_secret)
        form.addRow("ID platform:", self.acc_extra_id)
        form.addRow("Nama cookie:", self.acc_cookie_name)
        save = QPushButton("💾 Simpan Akun")
        save.clicked.connect(self._save_account)
        form.addRow(save)
        form.addRow(QLabel(
            "browser = login sekali di jendela yang terbuka, sesi tersimpan lokal.\n"
            "cookie  = paste nilai cookie (lanjutan, risiko checkpoint lebih tinggi).\n"
            "api     = Meta Graph API (IG/Threads/FB Page) - lihat PANDUAN-AKUN.md.\n"
            "Semua rahasia terenkripsi DPAPI di PC ini, tidak dikirim ke mana pun."))
        split.addWidget(form_w)
        lay.addWidget(split)
        return w

    def _save_account(self):
        platform = self.acc_platform.currentText()
        label = self.acc_label.text().strip() or platform
        extra = {}
        extra_id = self.acc_extra_id.text().strip()
        if extra_id:
            key = {"instagram": "ig_user_id", "threads": "threads_user_id",
                   "facebook": "page_id"}.get(platform)
            if key:
                extra[key] = extra_id
        if self.acc_mode.currentText() == "cookie":
            extra["cookie_name"] = self.acc_cookie_name.text().strip() or "sessionid"
            extra["cookie_domain"] = {
                "tiktok": ".tiktok.com", "youtube": ".youtube.com",
                "instagram": ".instagram.com", "facebook": ".facebook.com",
                "threads": ".threads.net"}[platform]
        self.store.upsert_account(Account(
            platform=platform, label=label, mode=self.acc_mode.currentText(),
            secret=self.acc_secret.toPlainText().strip(), extra=extra))
        self._log(f"Akun tersimpan: {label}")
        self._refresh_accounts()

    def _selected_account(self) -> Account | None:
        row = self.accounts_table.currentRow()
        if row < 0:
            return None
        accounts = self.store.load_accounts()
        return accounts[row] if row < len(accounts) else None

    def _delete_account(self):
        acc = self._selected_account()
        if acc and QMessageBox.question(
                self, "Hapus", f"Hapus akun {acc.label}?") == QMessageBox.Yes:
            self.store.delete_account(acc.id)
            self._refresh_accounts()

    def _login_selected(self):
        acc = self._selected_account()
        if not acc:
            QMessageBox.warning(self, "Akun", "Pilih akun di tabel dulu.")
            return
        if acc.mode == "api":
            QMessageBox.information(self, "Mode API",
                                    "Mode API tidak pakai login browser - cukup token.")
            return
        self._log(f"Membuka login {acc.platform} untuk {acc.label}... "
                  "Login sendiri di jendela browser, lalu tutup jendelanya.")
        self.login_worker = LoginWorker(self.store, acc)
        self.login_worker.done.connect(self._log)
        self.login_worker.start()

    def _refresh_accounts(self):
        accounts = self.store.load_accounts()
        self.accounts_table.setRowCount(len(accounts))
        for cb in self.account_checks.values():
            cb.setParent(None)
        self.account_checks.clear()
        for i, acc in enumerate(accounts):
            info = (acc.extra.get("ig_user_id") or acc.extra.get("threads_user_id")
                    or acc.extra.get("page_id") or "-")
            for j, val in enumerate([acc.platform, acc.label, acc.mode, info]):
                self.accounts_table.setItem(i, j, QTableWidgetItem(str(val)))
            cb = QCheckBox(f"{PLATFORM_LABELS[acc.platform]} — {acc.label} ({acc.mode})")
            cb.setChecked(True)
            self.accounts_box.addWidget(cb)
            self.account_checks[acc.id] = cb

    # ---------------------------------------------------------------- history
    def _history_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.jobs_label = QLabel()
        lay.addWidget(self.jobs_label)
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(
            ["Waktu", "Platform", "Status", "Pesan / Link"])
        lay.addWidget(self.history_table)
        btn = QPushButton("🔄 Muat Ulang")
        btn.clicked.connect(self._refresh_history)
        lay.addWidget(btn)
        return w

    def _refresh_history(self):
        jobs = self.store.load_jobs()
        self.jobs_label.setText(
            "Job terjadwal: " + ("; ".join(
                f"{time.strftime('%d/%m %H:%M', time.localtime(j.scheduled_at))} "
                f"({len(j.account_ids)} akun)" for j in jobs) or "tidak ada"))
        rows = list(reversed(self.store.load_history()))
        self.history_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            when = time.strftime("%d/%m %H:%M", time.localtime(r.get("at", 0)))
            msg = r.get("message", "") + (f" {r['url']}" if r.get("url") else "")
            for j, val in enumerate([when, r.get("platform", ""),
                                     r.get("status", ""), msg]):
                self.history_table.setItem(i, j, QTableWidgetItem(str(val)))


def run():
    import sys
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

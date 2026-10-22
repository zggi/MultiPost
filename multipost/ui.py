"""PySide6 desktop UI v1.3 - interactive dark dashboard.

Layout: left sidebar navigation + stacked pages.
Compose page: drag-&-drop video zone, clickable platform cards (toggle),
live per-platform character counters, a phone-style live preview, and
per-platform live progress while publishing.

Business rules kept from v1:
- Publish asks ONE confirmation showing the exact adapted versions.
- Publishing runs in a worker thread; a publish in flight cannot restart.
- Results arrive per platform (engine on_result) - never one silent block.
"""

from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateTimeEdit, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSplitter,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import PLATFORM_LABELS, PLATFORMS, __version__
from .bootstrap import detect_system_browser
from .captions import LIMITS, adapt
from .engine import open_login_for, publish_job
from .models import Account, Job
from .store import Store

PLATFORM_COLORS = {
    "instagram": "#E1306C",
    "threads": "#E7E7E7",
    "facebook": "#1877F2",
    "tiktok": "#FE2C55",
    "youtube": "#FF3B30",
}
PLATFORM_ICONS = {
    "instagram": "📸", "threads": "🧵", "facebook": "👍",
    "tiktok": "🎵", "youtube": "▶️",
}

THEME = """
* { font-family: "Segoe UI", sans-serif; color: #E8EAF2; }
QMainWindow, QWidget { background: #0E1120; }
QFrame#sidebar { background: #141830; border-right: 1px solid #23264A; }
QLabel#logo { font-size: 22px; font-weight: 800; color: #FFFFFF; }
QLabel#sub { color: #8B90B8; font-size: 11px; }
QPushButton#nav { text-align: left; padding: 11px 14px; border-radius: 10px;
    background: transparent; border: none; font-size: 14px; color: #B9BCE0; }
QPushButton#nav:hover { background: #1D2142; color: #FFFFFF; }
QPushButton#nav[active="true"] { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
    stop:0 #6D5DF6, stop:1 #9A5CF6); color: #FFFFFF; font-weight: 700; }
QFrame#card { background: #171B36; border: 1px solid #262A52; border-radius: 14px; }
QFrame#card:hover { border-color: #3A3F78; }
QFrame#dropzone { background: #151938; border: 2px dashed #3A3F78; border-radius: 14px; }
QFrame#dropzone:hover { border-color: #6D5DF6; background: #181D42; }
QLineEdit, QPlainTextEdit, QComboBox, QDateTimeEdit {
    background: #12152C; border: 1px solid #2A2E57; border-radius: 9px;
    padding: 8px 10px; selection-background-color: #6D5DF6; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #6D5DF6; }
QPushButton { background: #23264A; border: 1px solid #33376B; border-radius: 10px;
    padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #2B2F5C; }
QPushButton#publish { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
    stop:0 #6D5DF6, stop:1 #00C2A8); border: none; color: white;
    font-size: 16px; font-weight: 800; padding: 13px; border-radius: 12px; }
QPushButton#publish:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
    stop:0 #7E6FF8, stop:1 #00D4B8); }
QPushButton#publish:disabled { background: #2A2E57; color: #8B90B8; }
QTableWidget { background: #12152C; border: 1px solid #262A52; border-radius: 10px;
    gridline-color: #23264A; }
QHeaderView::section { background: #1A1E3D; padding: 7px; border: none; font-weight: 700; }
QProgressBar { background: #12152C; border: 1px solid #2A2E57; border-radius: 6px;
    height: 12px; text-align: center; font-size: 9px; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
    stop:0 #6D5DF6, stop:1 #00C2A8); border-radius: 6px; }
QCheckBox { spacing: 7px; }
QScrollArea { border: none; }
QLabel#hint { color: #8B90B8; font-size: 11px; }
QLabel#counter { font-size: 11px; font-weight: 700; padding: 3px 9px;
    border-radius: 8px; background: #1A1E3D; }
"""


class DropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("dropzone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        self.icon = QLabel("🎬")
        self.icon.setStyleSheet("font-size: 34px;")
        self.icon.setAlignment(Qt.AlignCenter)
        self.text = QLabel("Tarik & letakkan video di sini, atau klik untuk memilih")
        self.text.setAlignment(Qt.AlignCenter)
        self.text.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.sub = QLabel("MP4 / MOV vertikal 9:16 — untuk Reels, TikTok & Shorts")
        self.sub.setObjectName("hint")
        self.sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.icon)
        lay.addWidget(self.text)
        lay.addWidget(self.sub)
        self.setMinimumHeight(118)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith((".mp4", ".mov", ".webm")):
                self.file_dropped.emit(path)
                return

    def mousePressEvent(self, _):
        self.file_dropped.emit("")  # empty = open file dialog (handled by parent)

    def set_file(self, path: str):
        size_mb = os.path.getsize(path) / 1_000_000 if os.path.isfile(path) else 0
        self.icon.setText("✅")
        self.text.setText(os.path.basename(path))
        self.sub.setText(f"{size_mb:.1f} MB — klik untuk ganti video")


class PlatformCard(QFrame):
    toggled = Signal(str, bool)

    def __init__(self, account: Account):
        super().__init__()
        self.account = account
        self.checked = True
        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        color = PLATFORM_COLORS[account.platform]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(13, 10, 13, 10)
        top = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 15px;")
        name = QLabel(f"{PLATFORM_ICONS[account.platform]} {PLATFORM_LABELS[account.platform]}")
        name.setStyleSheet("font-weight: 700; font-size: 13px;")
        self.check = QLabel("✓ ON")
        self.check.setStyleSheet(
            "background: #00C2A8; color: #06231E; font-weight: 800; "
            "padding: 2px 9px; border-radius: 8px; font-size: 11px;")
        top.addWidget(dot)
        top.addWidget(name)
        top.addStretch()
        top.addWidget(self.check)
        lay.addLayout(top)
        label = QLabel(f"{account.label}  ·  mode {account.mode}")
        label.setObjectName("hint")
        lay.addWidget(label)
        self.status = QLabel("")
        self.status.setStyleSheet("font-size: 11px; font-weight: 600;")
        lay.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        lay.addWidget(self.bar)
        self._paint()

    def _paint(self):
        color = PLATFORM_COLORS[self.account.platform]
        if self.checked:
            self.setStyleSheet(
                f"QFrame#card {{ border: 2px solid {color}; background: #1A1E3D; "
                "border-radius: 14px; }")
            self.check.setText("✓ ON")
            self.check.setStyleSheet(
                "background: #00C2A8; color: #06231E; font-weight: 800; "
                "padding: 2px 9px; border-radius: 8px; font-size: 11px;")
        else:
            self.setStyleSheet("")
            self.check.setText("OFF")
            self.check.setStyleSheet(
                "background: #2A2E57; color: #8B90B8; font-weight: 800; "
                "padding: 2px 9px; border-radius: 8px; font-size: 11px;")

    def mousePressEvent(self, _):
        self.checked = not self.checked
        self._paint()
        self.toggled.emit(self.account.id, self.checked)

    def set_running(self):
        self.bar.setVisible(True)
        self.bar.setRange(0, 0)
        self.status.setText("⏳ Sedang publish...")
        self.status.setStyleSheet("color: #FFC94D; font-size: 11px; font-weight: 600;")

    def set_result(self, result: dict):
        self.bar.setRange(0, 100)
        if result["status"] in ("success", "dry_run"):
            self.bar.setValue(100)
            self.status.setText(f"✅ {result['message'][:90]}")
            self.status.setStyleSheet("color: #2EE6A8; font-size: 11px; font-weight: 600;")
        else:
            self.bar.setValue(0)
            self.status.setText(f"❌ {result['message'][:90]}")
            self.status.setStyleSheet("color: #FF6B81; font-size: 11px; font-weight: 600;")

    def reset_status(self):
        self.bar.setVisible(False)
        self.status.setText("")


class PublishWorker(QThread):
    log = Signal(str)
    progress = Signal(dict)
    done = Signal(list)

    def __init__(self, store: Store, job: Job, accounts: list[Account]):
        super().__init__()
        self.store, self.job, self.accounts = store, job, accounts

    def run(self):
        results = publish_job(
            self.store, self.job, self.accounts, log=self.log.emit,
            on_result=lambda r: self.progress.emit(r.to_dict()))
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
        except Exception as e:
            self.done.emit(f"Login gagal: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"MultiPost v{__version__} — 1 Video, 5 Platform")
        self.resize(1160, 780)
        self.store = Store()
        self.worker: PublishWorker | None = None
        self.login_worker: LoginWorker | None = None
        self.cards: dict[str, PlatformCard] = {}
        self.video_path = ""
        self.preview_platform = "tiktok"

        root = QWidget()
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self._sidebar())
        self.pages = QStackedWidget()
        self.pages.addWidget(self._compose_page())
        self.pages.addWidget(self._accounts_page())
        self.pages.addWidget(self._history_page())
        main.addWidget(self.pages, 1)
        self.setCentralWidget(root)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_schedule)
        self.timer.start(30_000)
        self._goto(0)
        self._refresh_accounts()
        self._refresh_history()
        self._update_counters()

    # ------------------------------------------------------------- sidebar
    def _sidebar(self) -> QFrame:
        sb = QFrame()
        sb.setObjectName("sidebar")
        sb.setFixedWidth(208)
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(16, 20, 16, 16)
        logo = QLabel("🚀 MultiPost")
        logo.setObjectName("logo")
        lay.addWidget(logo)
        sub = QLabel("1 video → 5 platform")
        sub.setObjectName("sub")
        lay.addWidget(sub)
        lay.addSpacing(22)
        self.nav_btns = []
        for i, (icon, text) in enumerate(
                [("📤", "Posting"), ("🔑", "Akun"), ("🕘", "Riwayat")]):
            b = QPushButton(f"{icon}  {text}")
            b.setObjectName("nav")
            b.clicked.connect(lambda _=False, idx=i: self._goto(idx))
            lay.addWidget(b)
            self.nav_btns.append(b)
        lay.addStretch()
        engine = detect_system_browser()
        engine_name = {"msedge": "Microsoft Edge (ringan)",
                       "chrome": "Google Chrome"}.get(engine or "", "Chromium")
        info = QLabel(f"🌐 Browser sesi: {engine_name}\n🔒 Akun terenkripsi DPAPI\n"
                      f"📦 Versi {__version__}")
        info.setObjectName("hint")
        info.setWordWrap(True)
        lay.addWidget(info)
        return sb

    def _goto(self, idx: int):
        self.pages.setCurrentIndex(idx)
        for i, b in enumerate(self.nav_btns):
            b.setProperty("active", "true" if i == idx else "false")
            b.style().unpolish(b)
            b.style().polish(b)

    # ------------------------------------------------------------- compose
    def _compose_page(self) -> QWidget:
        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(12)
        self.dropzone = DropZone()
        self.dropzone.file_dropped.connect(self._on_drop)
        left.addWidget(self.dropzone)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Judul YouTube (opsional — kosong = baris pertama caption)")
        self.title_edit.textChanged.connect(self._update_preview)
        left.addWidget(self.title_edit)
        self.media_url_edit = QLineEdit()
        self.media_url_edit.setPlaceholderText("URL publik video (wajib hanya untuk akun Meta mode API)")
        left.addWidget(self.media_url_edit)

        cap_head = QHBoxLayout()
        cap_head.addWidget(QLabel("<b>Caption</b> — soft selling: cerita dulu, CTA follow/komen/tag"))
        cap_head.addStretch()
        left.addLayout(cap_head)
        self.caption_edit = QPlainTextEdit()
        self.caption_edit.setPlaceholderText("Tulis caption di sini…")
        self.caption_edit.setMaximumHeight(120)
        self.caption_edit.textChanged.connect(self._update_counters)
        left.addWidget(self.caption_edit)
        self.counter_row = QHBoxLayout()
        self.counter_row.setSpacing(6)
        left.addLayout(self.counter_row)

        left.addWidget(QLabel("<b>Posting ke</b> — klik kartu untuk ON/OFF"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(238)
        self.cards_host = QWidget()
        self.cards_lay = QVBoxLayout(self.cards_host)
        self.cards_lay.setContentsMargins(0, 0, 0, 0)
        self.cards_lay.setSpacing(8)
        scroll.setWidget(self.cards_host)
        left.addWidget(scroll)

        sched = QHBoxLayout()
        self.schedule_check = QCheckBox("Jadwalkan pada:")
        self.schedule_edit = QDateTimeEdit()
        self.schedule_edit.setCalendarPopup(True)
        from PySide6.QtCore import QDateTime
        self.schedule_edit.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        sched.addWidget(self.schedule_check)
        sched.addWidget(self.schedule_edit)
        sched.addStretch()
        left.addLayout(sched)

        self.publish_btn = QPushButton("🚀  POSTING SEKARANG")
        self.publish_btn.setObjectName("publish")
        self.publish_btn.clicked.connect(self._publish_clicked)
        left.addWidget(self.publish_btn)
        self.banner = QLabel("")
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet("font-weight: 700;")
        left.addWidget(self.banner)

        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(QLabel("<b>👀 Preview</b>"))
        right.addWidget(self._preview_card())
        right.addWidget(QLabel("<b>📜 Log</b>"))
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        right.addWidget(self.log_edit, 1)

        outer.addLayout(left, 3)
        outer.addLayout(right, 2)
        return page

    def _preview_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumWidth(300)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        chips = QHBoxLayout()
        self.preview_btns = {}
        for p in PLATFORMS:
            b = QPushButton(PLATFORM_ICONS[p])
            b.setFixedWidth(40)
            b.clicked.connect(lambda _=False, pl=p: self._set_preview(pl))
            chips.addWidget(b)
            self.preview_btns[p] = b
        chips.addStretch()
        lay.addLayout(chips)
        self.pv_account = QLabel("@akun")
        self.pv_account.setStyleSheet("font-weight: 800; font-size: 14px;")
        lay.addWidget(self.pv_account)
        media = QFrame()
        media.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #23264A, "
            "stop:1 #3A2A6B); border-radius: 12px; min-height: 190px;")
        ml = QVBoxLayout(media)
        ml.setAlignment(Qt.AlignCenter)
        play = QLabel("▶")
        play.setStyleSheet("font-size: 40px; color: white;")
        play.setAlignment(Qt.AlignCenter)
        self.pv_file = QLabel("belum ada video")
        self.pv_file.setObjectName("hint")
        self.pv_file.setAlignment(Qt.AlignCenter)
        ml.addWidget(play)
        ml.addWidget(self.pv_file)
        lay.addWidget(media)
        self.pv_caption = QLabel("Caption akan muncul di sini…")
        self.pv_caption.setWordWrap(True)
        lay.addWidget(self.pv_caption)
        self.pv_meta = QLabel("")
        self.pv_meta.setObjectName("hint")
        self.pv_meta.setWordWrap(True)
        lay.addWidget(self.pv_meta)
        self._set_preview("tiktok")
        return card

    def _set_preview(self, platform: str):
        self.preview_platform = platform
        for p, b in self.preview_btns.items():
            b.setStyleSheet(
                f"background: {PLATFORM_COLORS[p]}; color: white; font-weight: 800;"
                if p == platform else "")
        self._update_preview()

    def _on_drop(self, path: str):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, "Pilih video", "", "Video (*.mp4 *.mov *.webm)")
        if path and os.path.isfile(path):
            self.video_path = path
            self.dropzone.set_file(path)
            self._update_preview()

    def _selected_ids(self) -> list[str]:
        return [aid for aid, card in self.cards.items() if card.checked]

    def _update_counters(self):
        # Chips are created ONCE per platform and only their text is updated.
        # (Recreating them per keystroke orphaned the old widgets - removed
        # from the layout but still visible, floating over the window.)
        if not hasattr(self, "_counter_chips"):
            self._counter_chips: dict[str, QLabel] = {}
        caption = self.caption_edit.toPlainText()
        platforms = []
        for acc in self.store.load_accounts():
            if acc.platform not in platforms:
                platforms.append(acc.platform)
        for platform in platforms:
            ad = adapt(platform, caption, self.title_edit.text())
            limit = (LIMITS["youtube_title"] if platform == "youtube"
                     else LIMITS.get(platform, 2200))
            n = len(ad.title) if platform == "youtube" else len(ad.text)
            color = "#2EE6A8" if n <= limit else "#FF6B81"
            chip = self._counter_chips.get(platform)
            if chip is None:
                chip = QLabel()
                chip.setObjectName("counter")
                self._counter_chips[platform] = chip
                # Insert before the trailing stretch (added in _compose_page
                # via the first call below) - simply append; order is cosmetic.
                self.counter_row.addWidget(chip)
            chip.setText(f"{PLATFORM_ICONS[platform]} {n}/{limit}")
            chip.setStyleSheet(f"color: {color}; background: #1A1E3D; "
                               "padding: 3px 9px; border-radius: 8px; font-weight: 700;")
        self._update_preview()

    def _update_preview(self):
        accounts = self.store.load_accounts()
        acc = next((a for a in accounts if a.platform == self.preview_platform), None)
        self.pv_account.setText(
            f"{PLATFORM_ICONS[self.preview_platform]} {acc.label if acc else '(belum ada akun)'}")
        self.pv_file.setText(os.path.basename(self.video_path) if self.video_path
                             else "belum ada video")
        ad = adapt(self.preview_platform, self.caption_edit.toPlainText(),
                   self.title_edit.text())
        text = (ad.title + "\n" if ad.title and self.preview_platform == "youtube" else "") + ad.text
        self.pv_caption.setText(text or "Caption akan muncul di sini…")
        warn = " ".join(ad.warnings)
        self.pv_meta.setText(
            f"{PLATFORM_LABELS[self.preview_platform]} · {len(ad.text)} karakter"
            + (f" · ⚠️ {warn}" if warn else ""))

    # ------------------------------------------------------------- publish
    def _publish_clicked(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Sabar", "Publish sebelumnya masih berjalan.")
            return
        if not self.video_path or not os.path.isfile(self.video_path):
            QMessageBox.warning(self, "Video", "Pilih / letakkan file video dulu.")
            return
        selected = self._selected_ids()
        if not selected:
            QMessageBox.warning(self, "Akun", "Nyalakan minimal 1 kartu platform.")
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
        msg = (f"Posting {when}?\n\nVideo: {os.path.basename(self.video_path)}\n"
               + "\n".join(lines) + "\n\nKlik Yes untuk menerbitkan persis versi ini.")
        if QMessageBox.question(self, "Konfirmasi Publish", msg) != QMessageBox.Yes:
            return
        job = Job(video_path=self.video_path,
                  caption=self.caption_edit.toPlainText(),
                  title=self.title_edit.text(),
                  media_url=self.media_url_edit.text().strip(),
                  account_ids=selected)
        if scheduled:
            job.scheduled_at = self.schedule_edit.dateTime().toSecsSinceEpoch()
            self.store.add_job(job)
            self._log(f"Job dijadwalkan: {time.strftime('%d/%m %H:%M', time.localtime(job.scheduled_at))}")
            self._refresh_history()
            self.banner.setText("🗓️ Job masuk antrean jadwal.")
            self.banner.setStyleSheet("color: #FFC94D; font-weight: 700;")
            return
        for aid in selected:
            self.cards[aid].reset_status()
        self._run_job(job)

    def _run_job(self, job: Job):
        accounts = self.store.load_accounts()
        self.publish_btn.setEnabled(False)
        self.publish_btn.setText("⏳  SEDANG PUBLISH…")
        for aid in job.account_ids:
            if aid in self.cards:
                self.cards[aid].set_running()
        self.worker = PublishWorker(self.store, job, accounts)
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._publish_done)
        self.worker.start()

    def _on_progress(self, result: dict):
        for card in self.cards.values():
            if card.account.label == result["account_label"] and \
                    card.account.platform == result["platform"]:
                card.set_result(result)

    def _publish_done(self, results: list):
        self.publish_btn.setEnabled(True)
        self.publish_btn.setText("🚀  POSTING SEKARANG")
        ok_n = sum(1 for r in results if r["status"] == "success")
        self.banner.setText(f"🎉 Selesai: {ok_n}/{len(results)} platform berhasil. "
                            "Detail di kartu & tab Riwayat.")
        self.banner.setStyleSheet(
            f"color: {'#2EE6A8' if ok_n == len(results) else '#FFC94D'}; font-weight: 700;")
        self._refresh_history()

    def _check_schedule(self):
        now = time.time()
        for job in self.store.load_jobs():
            if job.scheduled_at and job.scheduled_at <= now:
                self.store.remove_job(job.id)
                self._log("Menjalankan job terjadwal...")
                self._run_job(job)

    def _log(self, text: str):
        self.log_edit.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {text}")

    # ------------------------------------------------------------- accounts
    def _accounts_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 16, 18, 16)
        split = QSplitter()
        self.accounts_table = QTableWidget(0, 4)
        self.accounts_table.setHorizontalHeaderLabels(
            ["Platform", "Label", "Mode", "ID/Info"])
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel("<b>Akun tersimpan</b>"))
        ll.addWidget(self.accounts_table)
        del_btn = QPushButton("🗑️ Hapus Akun Terpilih")
        del_btn.clicked.connect(self._delete_account)
        ll.addWidget(del_btn)
        login_btn = QPushButton("🌐 Login Browser (akun terpilih)")
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
        hint = QLabel(
            "browser = login sekali di Edge, sesi tersimpan lokal & ringan.\n"
            "cookie  = paste nilai cookie / JSON Cookie-Editor (risiko checkpoint).\n"
            "api     = Meta Graph API (IG/Threads/FB Page) — lihat PANDUAN-AKUN.md.\n"
            "Semua rahasia terenkripsi DPAPI di PC ini, tidak dikirim ke mana pun.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        form.addRow(hint)
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
                                    "Mode API tidak pakai login browser — cukup token.")
            return
        self._log(f"Membuka login {acc.platform} untuk {acc.label}… "
                  "Login sendiri di jendela browser, lalu tutup jendelanya.")
        self.login_worker = LoginWorker(self.store, acc)
        self.login_worker.done.connect(self._log)
        self.login_worker.start()

    def _refresh_accounts(self):
        accounts = self.store.load_accounts()
        self.accounts_table.setRowCount(len(accounts))
        for i, acc in enumerate(accounts):
            info = (acc.extra.get("ig_user_id") or acc.extra.get("threads_user_id")
                    or acc.extra.get("page_id") or "-")
            for j, val in enumerate([acc.platform, acc.label, acc.mode, info]):
                self.accounts_table.setItem(i, j, QTableWidgetItem(str(val)))
        # Rebuild platform cards on the compose page. Detach explicitly -
        # deleteLater alone leaves removed widgets visible until the event
        # loop gets to them.
        while self.cards_lay.count():
            item = self.cards_lay.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self.cards.clear()
        if not accounts:
            empty = QLabel("Belum ada akun — tambah di tab Akun (sidebar).")
            empty.setObjectName("hint")
            self.cards_lay.addWidget(empty)
        for acc in accounts:
            card = PlatformCard(acc)
            card.toggled.connect(lambda _aid, _on: self._update_preview())
            self.cards_lay.addWidget(card)
            self.cards[acc.id] = card
        self._update_counters()

    # ------------------------------------------------------------- history
    def _history_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 16, 18, 16)
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
            "🗓️ Job terjadwal: " + ("; ".join(
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
    app.setStyleSheet(THEME)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0E1120"))
    app.setPalette(palette)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

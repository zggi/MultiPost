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

from PySide6.QtCore import (QEasingCurve, QPropertyAnimation, Qt, QThread,
                            QTimer, Signal)
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateTimeEdit, QDialog, QFileDialog,
    QFormLayout,
    QFrame, QGraphicsOpacityEffect, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QProgressDialog, QPushButton, QScrollArea, QSplitter,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import PLATFORM_LABELS, PLATFORMS, __version__
from .bootstrap import detect_system_browser
from .captions import LIMITS, adapt
from .engine import open_login_for, publish_job
from .models import Account, Job
from .store import Store
from .updater import check_latest, download_setup, launch_installer

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
        self.text = QLabel("Tarik & letakkan video / gambar di sini, atau klik untuk memilih")
        self.text.setAlignment(Qt.AlignCenter)
        self.text.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.sub = QLabel("Video MP4/MOV 9:16 atau gambar JPG/PNG — YouTube khusus video")
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
            if path.lower().endswith((".mp4", ".mov", ".webm",
                                      ".jpg", ".jpeg", ".png", ".webp")):
                self.file_dropped.emit(path)
                return

    def mousePressEvent(self, _):
        self.file_dropped.emit("")  # empty = open file dialog (handled by parent)

    def set_file(self, path: str):
        from .models import media_kind
        size_mb = os.path.getsize(path) / 1_000_000 if os.path.isfile(path) else 0
        self.icon.setText("🖼️" if media_kind(path) == "image" else "🎬")
        self.text.setText(os.path.basename(path))
        self.sub.setText(f"{size_mb:.1f} MB — klik untuk ganti file")


class OverrideDialog(QDialog):
    """Per-account content override: optional own media and/or caption.
    Empty fields = fall back to the master content for that part."""

    def __init__(self, parent, account: Account, current: dict):
        super().__init__(parent)
        self.setWindowTitle(f"Konten khusus — {account.label}")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Kosongkan salah satu = pakai konten utama untuk bagian itu."))
        self.file_edit = QLineEdit(current.get("video_path", ""))
        self.file_edit.setPlaceholderText("File khusus akun ini (opsional — kosong = file utama)")
        pick = QPushButton("📁 Pilih file…")
        pick.clicked.connect(self._pick)
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_edit, 1)
        file_row.addWidget(pick)
        lay.addLayout(file_row)
        self.cap_edit = QPlainTextEdit(current.get("caption", ""))
        self.cap_edit.setPlaceholderText("Caption khusus akun ini (opsional — kosong = caption utama)")
        self.cap_edit.setMaximumHeight(110)
        lay.addWidget(self.cap_edit)
        btns = QHBoxLayout()
        save = QPushButton("💾 Simpan")
        save.clicked.connect(self.accept)
        clear = QPushButton("🗑️ Hapus override")
        clear.clicked.connect(self._clear)
        btns.addWidget(save)
        btns.addWidget(clear)
        lay.addLayout(btns)
        self.result: dict | None = None

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih media khusus",
            "", "Media (*.mp4 *.mov *.webm *.jpg *.jpeg *.png *.webp)")
        if path:
            self.file_edit.setText(path)

    def _clear(self):
        self.result = {}
        self.reject()

    def accept(self):
        self.result = {
            "video_path": self.file_edit.text().strip(),
            "caption": self.cap_edit.toPlainText().strip(),
        }
        super().accept()


class PlatformCard(QFrame):
    toggled = Signal(str, bool)
    override_clicked = Signal(str)

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
        bottom = QHBoxLayout()
        self.override_badge = QLabel("")
        self.override_badge.setStyleSheet(
            "background: #FFC94D; color: #3A2A00; font-weight: 800; "
            "padding: 1px 8px; border-radius: 8px; font-size: 11px;")
        self.override_badge.setVisible(False)
        ov_btn = QPushButton("✏️ Konten khusus")
        ov_btn.setObjectName("nav")
        # A child button consumes its own click, so this never toggles the card.
        ov_btn.clicked.connect(lambda: self.override_clicked.emit(self.account.id))
        bottom.addWidget(self.override_badge)
        bottom.addStretch()
        bottom.addWidget(ov_btn)
        lay.addLayout(bottom)
        self.status = QLabel("")
        self.status.setStyleSheet("font-size: 11px; font-weight: 600;")
        lay.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        lay.addWidget(self.bar)
        self._paint()

    def set_override(self, has_override: bool, media_name: str = ""):
        self.override_badge.setVisible(has_override)
        self.override_badge.setText(
            f"✏️ khusus{f' · {media_name}' if media_name else ''}")

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

    def __init__(self, store: Store, job: Job, accounts: list[Account],
                 settings: dict | None = None):
        super().__init__()
        self.store, self.job, self.accounts = store, job, accounts
        self.settings = settings

    def run(self):
        results = publish_job(
            self.store, self.job, self.accounts, log=self.log.emit,
            on_result=lambda r: self.progress.emit(r.to_dict()),
            settings=self.settings)
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
            from .publishers.base import friendly_error
            self.done.emit(f"Login gagal: {friendly_error(e) or e}")


class UpdateCheckWorker(QThread):
    found = Signal(object)  # update info dict or None

    def run(self):
        self.found.emit(check_latest(__version__))


class UpdateDownloadWorker(QThread):
    progress = Signal(int, int)  # done_bytes, total_bytes
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, info: dict):
        super().__init__()
        self.info = info

    def run(self):
        try:
            path = download_setup(
                self.info,
                progress=lambda d, t: self.progress.emit(d, t))
            self.done.emit(path)
        except Exception as e:
            self.failed.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"MultiPost v{__version__} — 1 Video, 5 Platform")
        self.resize(1160, 780)
        self.store = Store()
        self.overrides: dict = {}  # account_id -> {"video_path", "caption"}
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
        # Auto-update check: once a day, silent when up-to-date/offline.
        QTimer.singleShot(3000, lambda: self._check_update(manual=False))
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
        self.update_btn = QPushButton("🔄  Cek Update")
        self.update_btn.setObjectName("nav")
        self.update_btn.clicked.connect(lambda: self._check_update(manual=True))
        lay.addWidget(self.update_btn)
        lay.addSpacing(8)
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
        self._fade(self.pages, 220)

    @staticmethod
    def _fade(widget, duration: int = 220):
        """Smooth page/card transition: fade opacity in instead of a hard cut."""
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(0.45)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutQuad)
        anim.start()
        widget._fade_anim = anim  # keep alive until it finishes

    # ---------------------------------------------------- auto-update
    def _check_update(self, manual: bool):
        import time as _time
        marker = os.path.join(self.store.data_dir, "last_update_check.txt")
        if not manual:
            try:
                with open(marker, encoding="utf-8") as fh:
                    if _time.time() - float(fh.read().strip() or 0) < 86_400:
                        return
            except Exception:
                pass
            try:
                with open(marker, "w", encoding="utf-8") as fh:
                    fh.write(str(_time.time()))
            except Exception:
                pass
        if manual:
            self.update_btn.setText("⏳  Mengecek…")
            self.update_btn.setEnabled(False)
        self._upd_worker = UpdateCheckWorker(self)

        def _on_found(info):
            if manual:
                self.update_btn.setText("🔄  Cek Update")
                self.update_btn.setEnabled(True)
            if info:
                self._offer_update(info)
            elif manual:
                QMessageBox.information(
                    self, "Update",
                    f"Kamu sudah memakai versi terbaru (v{__version__}).")

        self._upd_worker.found.connect(_on_found)
        self._upd_worker.start()

    def _offer_update(self, info: dict):
        notes = (f"\n\nCatatan rilis:\n{info['notes']}" if info.get("notes") else "")
        ans = QMessageBox.question(
            self, "Update Tersedia 🎉",
            f"MultiPost v{info['version']} tersedia (kamu: v{__version__})."
            f"{notes}\n\nUpdate sekarang? Software akan tertutup, installer "
            "berjalan, lalu buka lagi MultiPost dari shortcut.")
        if ans != QMessageBox.Yes:
            return
        dlg = QProgressDialog("Mengunduh update… 0 MB", "Batal", 0, 100, self)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        worker = UpdateDownloadWorker(info, self)

        def _progress(done_b: int, total_b: int):
            mb = done_b / 1_000_000
            if total_b:
                dlg.setValue(int(done_b * 100 / total_b))
                dlg.setLabelText(
                    f"Mengunduh update… {mb:.1f} / {total_b / 1_000_000:.1f} MB")
            else:
                dlg.setLabelText(f"Mengunduh update… {mb:.1f} MB")

        worker.progress.connect(_progress)
        dlg.canceled.connect(worker.terminate)

        def _done(path):
            dlg.close()
            launch_installer(path)
            QMessageBox.information(
                self, "Update",
                "Installer update dibuka. MultiPost akan ditutup — ikuti "
                "wizard-nya (folder install yang sama), lalu buka lagi "
                "MultiPost. Akun & login-mu aman, tidak tertimpa.")
            QApplication.quit()

        def _failed(msg):
            dlg.close()
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Update gagal")
            box.setText(f"Unduhan gagal: {msg}")
            box.setInformativeText(
                "Kamu bisa unduh manual dari halaman rilis resmi, "
                "lalu install seperti biasa (folder yang sama).")
            open_btn = box.addButton("🌐 Buka Halaman Rilis", QMessageBox.ActionRole)
            box.addButton("Tutup", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is open_btn:
                from PySide6.QtGui import QDesktopServices
                from PySide6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl(
                    "https://github.com/zggi/MultiPost/releases/latest"))

        worker.done.connect(_done)
        worker.failed.connect(_failed)
        self._dl_worker = worker
        worker.start()
        dlg.show()

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

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("⏱️ Jeda antar platform:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(0, 3600)
        self.interval_spin.setValue(60)
        self.interval_spin.setSuffix(" dtk")
        interval_row.addWidget(self.interval_spin)
        self.interval_random = QCheckBox("Acak ±50% (lebih natural)")
        self.interval_random.setChecked(True)
        interval_row.addWidget(self.interval_random)
        interval_row.addWidget(QLabel("— 0 = tanpa jeda. Jeda membuat posting "
                                      "tidak serentak & lebih aman dari limit."))
        interval_row.addStretch()
        left.addLayout(interval_row)

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
                self, "Pilih media", "",
                "Media (*.mp4 *.mov *.webm *.jpg *.jpeg *.png *.webp)")
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
            QMessageBox.warning(self, "Media", "Pilih / letakkan file media dulu.")
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
                  account_ids=selected,
                  overrides={aid: ov for aid, ov in self.overrides.items()
                             if aid in selected
                             and (ov.get("video_path") or ov.get("caption"))})
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
        # Persist the interval controls into settings, then hand them to the job.
        settings = self.store.load_settings()
        if hasattr(self, "interval_spin"):
            settings["interval_seconds"] = int(self.interval_spin.value())
            settings["interval_random"] = bool(self.interval_random.isChecked())
            self.store.save_settings(settings)
        self.publish_btn.setEnabled(False)
        self.publish_btn.setText("⏳  SEDANG PUBLISH…")
        for aid in job.account_ids:
            if aid in self.cards:
                self.cards[aid].set_running()
        self.worker = PublishWorker(self.store, job, accounts, settings=settings)
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._publish_done)
        self.worker.start()

    def _on_progress(self, result: dict):
        for card in self.cards.values():
            if card.account.label == result["account_label"] and \
                    card.account.platform == result["platform"]:
                card.set_result(result)
                self._fade(card, 300)

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

        # ---- global proxy -------------------------------------------------
        proxy_box = QGroupBox("🌐 Proxy (opsional — satu proxy untuk semua akun)")
        proxy_form = QFormLayout(proxy_box)
        settings = self.store.load_settings()
        proxy = settings.get("proxy", {})
        self.proxy_enabled = QCheckBox("Aktifkan proxy")
        self.proxy_enabled.setChecked(bool(proxy.get("enabled")))
        self.proxy_type = QComboBox()
        self.proxy_type.addItems(["http", "socks5"])
        self.proxy_type.setCurrentText(proxy.get("type") or "http")
        self.proxy_host = QLineEdit(proxy.get("host") or "")
        self.proxy_host.setPlaceholderText("mis. 103.12.34.56")
        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(1, 65535)
        self.proxy_port.setValue(int(proxy.get("port") or 8080))
        self.proxy_user = QLineEdit(proxy.get("username") or "")
        self.proxy_user.setPlaceholderText("opsional")
        self.proxy_pass = QLineEdit(proxy.get("password") or "")
        self.proxy_pass.setEchoMode(QLineEdit.Password)
        self.proxy_pass.setPlaceholderText("opsional")
        proxy_form.addRow(self.proxy_enabled)
        proxy_form.addRow("Jenis:", self.proxy_type)
        proxy_form.addRow("Host:", self.proxy_host)
        proxy_form.addRow("Port:", self.proxy_port)
        proxy_form.addRow("Username:", self.proxy_user)
        proxy_form.addRow("Password:", self.proxy_pass)
        proxy_save = QPushButton("💾 Simpan Pengaturan Proxy")
        proxy_save.clicked.connect(self._save_proxy)
        proxy_form.addRow(proxy_save)
        proxy_form.addRow(QLabel(
            "Proxy dipakai browser (Playwright) & API Meta. Kosong/nonaktif = "
            "koneksi langsung (paling stabil). Proxy mati = semua publish gagal, "
            "jadi aktifkan hanya bila perlu (mis. tiap akun beda IP). "
            "Password terenkripsi DPAPI di PC ini."))
        lay.addWidget(proxy_box)
        return w

    def _save_proxy(self):
        settings = self.store.load_settings()
        settings["proxy"] = {
            "enabled": bool(self.proxy_enabled.isChecked()),
            "type": self.proxy_type.currentText(),
            "host": self.proxy_host.text().strip(),
            "port": int(self.proxy_port.value()),
            "username": self.proxy_user.text().strip(),
            "password": self.proxy_pass.text(),
        }
        self.store.save_settings(settings)
        self._log("Pengaturan proxy tersimpan: "
                  + ("AKTIF " + settings["proxy"]["type"] + "://"
                     + settings["proxy"]["host"] + ":"
                     + str(settings["proxy"]["port"])
                     if settings["proxy"]["enabled"] and settings["proxy"]["host"]
                     else "NONAKTIF (koneksi langsung)"))

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
        if self.login_worker is not None and self.login_worker.isRunning():
            # One login window at a time: Chromium profiles are singletons -
            # a second launch on the same profile dies with ProcessSingleton
            # errors (seen in the wild 2026-10-23 00:48 log spam).
            QMessageBox.information(
                self, "Login sedang terbuka",
                "Jendela login masih terbuka. Selesaikan login di jendela "
                "itu (atau tutup jendelanya) sebelum membuka lagi.")
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
            card.override_clicked.connect(self._edit_override)
            ov = self.overrides.get(acc.id) or {}
            if ov.get("video_path") or ov.get("caption"):
                card.set_override(True, os.path.basename(ov["video_path"])
                                  if ov.get("video_path") else "")
            self.cards_lay.addWidget(card)
            self.cards[acc.id] = card
        self._update_counters()

    def _edit_override(self, account_id: str):
        accounts = {a.id: a for a in self.store.load_accounts()}
        acc = accounts.get(account_id)
        if not acc:
            return
        dlg = OverrideDialog(self, acc, self.overrides.get(account_id) or {})
        if dlg.exec() == QDialog.Accepted:
            result = dlg.result or {}
            if result.get("video_path") or result.get("caption"):
                self.overrides[account_id] = result
            else:
                self.overrides.pop(account_id, None)
        elif dlg.result == {}:
            # "Hapus override" pressed.
            self.overrides.pop(account_id, None)
        ov = self.overrides.get(account_id) or {}
        card = self.cards.get(account_id)
        if card:
            card.set_override(bool(ov.get("video_path") or ov.get("caption")),
                              os.path.basename(ov["video_path"])
                              if ov.get("video_path") else "")

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

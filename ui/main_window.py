"""Main application window for EMS Mail Fetcher."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QIntValidator, QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.settings import APP_NAME, APP_VERSION, RESULTS_DIR
from core.worker import WorkerManager
from ui.settings_dialog import load_settings, save_settings

log = logging.getLogger(__name__)

COLUMNS = ["#", "Mail", "Pass", "Server", "Status"]
WINDOW_W, WINDOW_H = 1060, 560
SIDEBAR_W = 160

STATUS_BG_DARK = {
    "finished": QColor("#1a3a2a"),
    "error":    QColor("#3a1a1a"),
    "stopping": QColor("#2a2a1a"),
    "running":  QColor("#1a2a3a"),
    "loaded":   QColor("#1e1e2e"),
}
STATUS_BG_LIGHT = {
    "finished": QColor("#d4f0dc"),
    "error":    QColor("#f0d4d4"),
    "stopping": QColor("#f0f0d4"),
    "running":  QColor("#d4e4f8"),
    "loaded":   QColor("#ffffff"),
}


class _UpdateSignals(QObject):
    found = pyqtSignal(str)


def _obscure(pw: str) -> str:
    if not pw:
        return "..."
    if len(pw) <= 3:
        return pw[0] + "..."
    return pw[:2] + "..." + pw[-1]


class MainWindow(QMainWindow):
    def __init__(self, licensed_to: str = "User", days_left: int = -1) -> None:
        super().__init__()

        self._licensed_to = licensed_to
        self._days_left = days_left

        if days_left == -1:
            days_str = "Lifetime"
        elif days_left > 0:
            days_str = f"{days_left} day{'s' if days_left != 1 else ''} left"
        else:
            days_str = "Expired"
        self.setWindowTitle(
            f"EMS Mail Fetcher  —  Licensed to: {licensed_to}  |  {days_str}"
        )

        self.setFixedSize(WINDOW_W, WINDOW_H)

        s = load_settings()
        self._dark_mode: bool = s.get("theme", "dark") == "dark"
        self._accounts: list[dict] = []
        self._row_map:  dict[int, int] = {}
        self._proxy_idx: int = 0
        self._session_emails: int = 0

        self._worker_manager = WorkerManager()
        self._connect_signals()

        # Central widget: sidebar | content(toolbar_row + table)
        central = QWidget()
        central.setObjectName("main_central")
        central_lay = QHBoxLayout(central)
        central_lay.setContentsMargins(0, 0, 0, 0)
        central_lay.setSpacing(0)

        central_lay.addWidget(self._build_sidebar())

        content = QWidget()
        content.setObjectName("main_content")
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(0)
        content_lay.addWidget(self._build_toolbar_row())
        self._update_bar = self._build_update_bar()
        content_lay.addWidget(self._update_bar)
        self._build_table()
        content_lay.addWidget(self._table)
        central_lay.addWidget(content)

        self.setCentralWidget(central)
        self._build_statusbar()
        self._apply_theme()

        self._stat_timer = QTimer(self)
        self._stat_timer.timeout.connect(self._refresh_stats)
        self._stat_timer.start(2000)

        # Kick off update check 3 s after window shows
        QTimer.singleShot(3000, self._check_for_updates)

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_W)

        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(0, 26, 0, 14)
        lay.setSpacing(0)

        # ── Logo: bolt + EMS wordmark ────────────────────────────────────────
        bolt = QLabel("⚡")
        bolt.setObjectName("sidebar_bolt")
        bolt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bolt_glow = QGraphicsDropShadowEffect(self)
        bolt_glow.setBlurRadius(20)
        bolt_glow.setColor(QColor("#0defa8"))
        bolt_glow.setOffset(0, 0)
        bolt.setGraphicsEffect(bolt_glow)
        lay.addWidget(bolt)

        lay.addSpacing(2)

        wm = QLabel("EMS")
        wm.setObjectName("sidebar_wordmark")
        wm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wm_glow = QGraphicsDropShadowEffect(self)
        wm_glow.setBlurRadius(28)
        wm_glow.setColor(QColor("#0defa8"))
        wm_glow.setOffset(0, 0)
        wm.setGraphicsEffect(wm_glow)
        lay.addWidget(wm)

        lay.addSpacing(8)

        r1 = QFrame()
        r1.setObjectName("sidebar_rule")
        r1.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(r1)

        lay.addSpacing(8)

        # ── Product name ─────────────────────────────────────────────────────
        product = QLabel("MAIL  FETCHER")
        product.setObjectName("sidebar_product")
        product.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(product)

        lay.addSpacing(8)

        r2 = QFrame()
        r2.setObjectName("sidebar_rule")
        r2.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(r2)

        lay.addSpacing(12)

        # ── Tagline ───────────────────────────────────────────────────────────
        tagline = QLabel("Precision\nInbox\nIntelligence")
        tagline.setObjectName("sidebar_tagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(tagline)

        lay.addStretch()

        # ── Buy EMS Mailer cross-promo ────────────────────────────────────────
        buy_btn = QPushButton("⚡  Get EMS Mailer")
        buy_btn.setObjectName("sidebar_buy_btn")
        buy_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/Retiredems/Ems-Mailer/releases/latest")
            )
        )
        lay.addWidget(buy_btn)

        lay.addSpacing(10)

        # ── License chip ──────────────────────────────────────────────────────
        if self._days_left == -1:
            lic_text = "♾  Lifetime"
            lic_obj = "sidebar_lic_good"
        elif self._days_left > 0:
            lic_text = f"⏳  {self._days_left} days left"
            lic_obj = "sidebar_lic_good"
        else:
            lic_text = "⚠  Expired"
            lic_obj = "sidebar_lic_warn"

        lic_lbl = QLabel(lic_text)
        lic_lbl.setObjectName(lic_obj)
        lic_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lic_lbl)

        lay.addSpacing(10)

        r3 = QFrame()
        r3.setObjectName("sidebar_rule")
        r3.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(r3)

        lay.addSpacing(6)

        footer = QLabel(
            '<a href="https://t.me/retiredems" '
            'style="color:#0defa8;text-decoration:none;font-weight:600;">@retiredems</a>'
        )
        footer.setObjectName("sidebar_footer")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setOpenExternalLinks(True)
        footer.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(footer)

        return sidebar

    # ── Toolbar row ───────────────────────────────────────────────────────────

    def _build_toolbar_row(self) -> QWidget:
        row = QWidget()
        row.setObjectName("toolbar_row")
        row.setFixedHeight(44)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(4)

        def _btn(label: str, slot, obj: str = "tb_btn") -> QPushButton:
            b = QPushButton(label)
            b.setObjectName(obj)
            b.clicked.connect(slot)
            return b

        def _sep() -> QFrame:
            f = QFrame()
            f.setObjectName("tb_sep")
            f.setFrameShape(QFrame.Shape.VLine)
            return f

        lay.addWidget(_btn("📂  Load", self._load_file))
        lay.addWidget(_sep())

        self._start_btn = _btn("▶  Start", self._start_all, "tb_btn_primary")
        lay.addWidget(self._start_btn)
        self._stop_btn = _btn("⏹  Stop", self._stop_all, "tb_btn_danger")
        lay.addWidget(self._stop_btn)

        lay.addWidget(_sep())

        tc_lbl = QLabel("Threads:")
        tc_lbl.setObjectName("tb_label")
        lay.addWidget(tc_lbl)

        saved_threads = load_settings().get("thread_count", 5)
        self._thread_edit = QLineEdit(str(saved_threads))
        self._thread_edit.setObjectName("tb_threads")
        self._thread_edit.setFixedWidth(36)
        self._thread_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thread_edit.setValidator(QIntValidator(1, 50))
        self._thread_edit.editingFinished.connect(self._save_thread_count)
        lay.addWidget(self._thread_edit)

        lay.addWidget(_sep())

        self._save_results_cb = QCheckBox("Save logins")
        self._save_results_cb.setObjectName("tb_check")
        self._save_results_cb.setMinimumWidth(95)
        lay.addWidget(self._save_results_cb)

        lay.addWidget(_sep())

        self._save_attachments_cb = QCheckBox("Attachments")
        self._save_attachments_cb.setObjectName("tb_check")
        self._save_attachments_cb.setMinimumWidth(100)
        lay.addWidget(self._save_attachments_cb)

        lay.addWidget(_sep())
        lay.addWidget(_btn("Proxy", self._open_proxy, "tb_btn_sec"))

        lay.addStretch()

        lay.addWidget(_btn("📁  Results", self._open_results_folder, "tb_btn_sec"))

        self._theme_btn = QPushButton("☀  Light" if self._dark_mode else "🌙  Dark")
        self._theme_btn.setObjectName("tb_btn_sec")
        self._theme_btn.clicked.connect(self._toggle_theme)
        lay.addWidget(self._theme_btn)

        return row

    # ── Update bar ────────────────────────────────────────────────────────────

    def _build_update_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("update_bar")
        bar.setFixedHeight(34)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 10, 0)
        lay.setSpacing(8)

        self._update_label = QLabel("")
        self._update_label.setObjectName("update_label")
        lay.addWidget(self._update_label)
        lay.addStretch()

        upd_btn = QPushButton("Update Now →")
        upd_btn.setObjectName("update_now_btn")
        upd_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/Retiredems/EMS-Mail-Fetcher/releases/latest")
            )
        )
        lay.addWidget(upd_btn)

        dismiss = QPushButton("Dismiss")
        dismiss.setObjectName("update_dismiss_btn")
        dismiss.clicked.connect(lambda: bar.setVisible(False))
        lay.addWidget(dismiss)

        bar.setVisible(False)
        return bar

    def _check_for_updates(self) -> None:
        import threading
        sigs = _UpdateSignals(self)
        sigs.found.connect(self._on_update_found)

        def _run():
            try:
                import urllib.request, json
                url = "https://api.github.com/repos/Retiredems/EMS-Mail-Fetcher/releases/latest"
                req = urllib.request.Request(url, headers={"User-Agent": "EMS-Mail-Fetcher"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read())
                latest = data.get("tag_name", "").lstrip("v")
                if latest and latest != APP_VERSION.lstrip("v"):
                    sigs.found.emit(latest)
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()

    def _on_update_found(self, version: str) -> None:
        self._update_label.setText(
            f"⬆  EMS Mail Fetcher v{version} is available  —  you're on v{APP_VERSION}"
        )
        self._update_bar.setVisible(True)

    # ── Table ─────────────────────────────────────────────────────────────────

    def _build_table(self) -> None:
        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        self._table.verticalHeader().setVisible(False)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setStretchLastSection(True)

        content_w = WINDOW_W - SIDEBAR_W
        self._table.setColumnWidth(0, 36)
        self._table.setColumnWidth(1, int(content_w * 0.21))
        self._table.setColumnWidth(2, int(content_w * 0.10))
        self._table.setColumnWidth(3, int(content_w * 0.21))

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._lbl_loaded  = QLabel("Loaded: 0")
        self._lbl_running = QLabel("Running: 0")
        self._lbl_done    = QLabel("Done: 0")
        self._lbl_emails  = QLabel("Emails: 0")
        for w in [self._lbl_loaded, self._lbl_running, self._lbl_done, self._lbl_emails]:
            sb.addWidget(w)
            sb.addWidget(_vsep())

    # ── Worker signals ────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        sig = self._worker_manager.signals
        sig.status_changed.connect(self._on_status)
        sig.server_detected.connect(self._on_server_detected)
        sig.finished.connect(self._on_finished)
        sig.error.connect(self._on_error)

    def _on_status(self, account_id: int, msg: str) -> None:
        self._set_cell(account_id, 4, msg)
        key = "error" if "error" in msg.lower() else "running"
        self._color_row(account_id, key)

    def _on_server_detected(self, account_id: int, server: str) -> None:
        self._set_cell(account_id, 3, server)

    def _on_finished(self, account_id: int, success: bool, contacts: int, emails: int, folders: int) -> None:
        if success:
            self._session_emails += contacts
            msg = f"done — {contacts:,} emails from {emails:,} mails in {folders} folders"
            self._set_cell(account_id, 4, msg)
            self._color_row(account_id, "finished")
        else:
            self._color_row(account_id, "error")
        self._refresh_stats()

    def _on_error(self, account_id: int, msg: str) -> None:
        self._set_cell(account_id, 4, f"error: {msg}")
        self._color_row(account_id, "error")

    # ── Load file ─────────────────────────────────────────────────────────────

    def _load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Account List", "",
            "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return
        self._parse_and_load(path)

    def _parse_and_load(self, path: str) -> None:
        from core.account_manager import add_account, lookup_domain_preset
        from db.database import get_session
        from db import repository as repo

        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        added = 0
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            if "," in line:
                email, password = line.split(",", 1)
            elif ":" in line:
                email, password = line.split(":", 1)
            else:
                continue

            email    = email.strip().lower()
            password = password.strip()
            if not email or "@" not in email:
                continue

            domain  = email.split("@", 1)[1]
            preset  = lookup_domain_preset(email) or {}
            imap    = preset.get("imap", {})
            server  = imap.get("server", f"imap.{domain}")
            port    = imap.get("port", 993)
            use_ssl = imap.get("ssl", True)

            account_id = None
            with get_session() as session:
                existing = repo.get_account_by_email(session, email)
                if existing:
                    account_id = existing.id
                    from core.account_manager import encrypt
                    repo.update_account(session, existing,
                                        encrypted_password=encrypt(password),
                                        server=server, port=port, use_ssl=use_ssl)

            if account_id is None:
                try:
                    account_id = add_account(
                        email=email, protocol="IMAP",
                        display_name=email,
                        server=server, port=port, use_ssl=use_ssl,
                        username=email, password=password,
                    )
                except Exception as exc:
                    log.warning("Could not add %s: %s", email, exc)
                    continue

            if account_id in self._row_map:
                row = self._row_map[account_id]
                self._table.item(row, 2).setText(_obscure(password))
                self._table.item(row, 3).setText(f"{server}:{port}")
                self._table.item(row, 4).setText("reloaded")
            else:
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._row_map[account_id] = row
                self._accounts.append({"id": account_id, "email": email, "password": password})

                def _cell(txt, align=Qt.AlignmentFlag.AlignLeft):
                    it = QTableWidgetItem(str(txt))
                    it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                    return it

                self._table.setItem(row, 0, _cell(row + 1, Qt.AlignmentFlag.AlignCenter))
                self._table.setItem(row, 1, _cell(email))
                self._table.setItem(row, 2, _cell(_obscure(password)))
                self._table.setItem(row, 3, _cell(f"{server}:{port}"))
                self._table.setItem(row, 4, _cell("loaded"))

            added += 1

        self._refresh_stats()
        self.statusBar().showMessage(f"Loaded {added} account(s) from file", 4000)

    # ── Start / Stop ──────────────────────────────────────────────────────────

    def _next_proxy(self, proxy_list: list) -> dict | None:
        if not proxy_list:
            return None
        p = proxy_list[self._proxy_idx % len(proxy_list)]
        self._proxy_idx += 1
        return p

    def _start_all(self) -> None:
        if not self._accounts:
            QMessageBox.information(self, "No Accounts", "Load an account list file first.")
            return
        self._session_emails = 0
        s = load_settings()
        proxy_list: list = s.get("proxy_list", [])
        save_results     = self._save_results_cb.isChecked()
        save_attachments = self._save_attachments_cb.isChecked()
        max_threads = self._thread_count()
        launched = 0

        for acct in self._accounts:
            if launched >= max_threads:
                break
            aid = acct["id"]
            if not self._worker_manager.is_running(aid):
                self._color_row(aid, "running")
                self._set_cell(aid, 4, "Connecting…")
                self._worker_manager.start_account(
                    aid,
                    save_eml=s.get("save_eml", True),
                    skip_duplicates=s.get("skip_duplicates", True),
                    proxy=self._next_proxy(proxy_list),
                    save_results=save_results,
                    save_attachments=save_attachments,
                )
                launched += 1

        self._queue = [a["id"] for a in self._accounts if not self._worker_manager.is_running(a["id"])]
        if hasattr(self, "_queue_timer"):
            self._queue_timer.stop()
        self._queue_timer = QTimer(self)
        self._queue_timer.timeout.connect(self._drain_queue)
        self._queue_timer.start(3000)

    def _drain_queue(self) -> None:
        if not self._queue:
            self._queue_timer.stop()
            return
        s = load_settings()
        proxy_list: list = s.get("proxy_list", [])
        save_results     = self._save_results_cb.isChecked()
        save_attachments = self._save_attachments_cb.isChecked()
        while self._queue and self._worker_manager.running_count() < self._thread_count():
            aid = self._queue.pop(0)
            if not self._worker_manager.is_running(aid):
                self._color_row(aid, "running")
                self._set_cell(aid, 4, "Connecting…")
                self._worker_manager.start_account(
                    aid,
                    save_eml=s.get("save_eml", True),
                    skip_duplicates=s.get("skip_duplicates", True),
                    proxy=self._next_proxy(proxy_list),
                    save_results=save_results,
                    save_attachments=save_attachments,
                )

    def _stop_all(self) -> None:
        if hasattr(self, "_queue_timer"):
            self._queue_timer.stop()
        self._queue = []
        self._worker_manager.stop_all()
        for aid, row in self._row_map.items():
            item = self._table.item(row, 4)
            if item and item.text() not in ("loaded", "reloaded") and \
               not item.text().startswith("done") and not item.text().startswith("error"):
                item.setText("stopping…")
                self._color_row(aid, "stopping")

    # ── Thread count ──────────────────────────────────────────────────────────

    def _thread_count(self) -> int:
        try:
            v = int(self._thread_edit.text())
            return max(1, min(v, 50))
        except ValueError:
            return 5

    def _save_thread_count(self) -> None:
        v = self._thread_count()
        self._thread_edit.setText(str(v))
        s = load_settings()
        s["thread_count"] = v
        save_settings(s)

    # ── Proxy / Theme / Results ───────────────────────────────────────────────

    def _open_proxy(self) -> None:
        from ui.proxy_dialog import ProxyDialog
        ProxyDialog(self).exec()

    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        self._theme_btn.setText("☀  Light" if self._dark_mode else "🌙  Dark")
        self._apply_theme()
        s = load_settings()
        s["theme"] = "dark" if self._dark_mode else "light"
        save_settings(s)

    def _apply_theme(self) -> None:
        from config.settings import RESOURCE_DIR
        base = RESOURCE_DIR / "ui"
        qss_file = base / ("styles.qss" if self._dark_mode else "styles_light.qss")
        if qss_file.exists():
            check_path = str(base / "check_white.svg").replace("\\", "/")
            css = qss_file.read_text(encoding="utf-8").replace(
                "CHECKMARK_PATH", f'"{check_path}"'
            )
            QApplication.instance().setStyleSheet(css)
        for aid, row in self._row_map.items():
            status_item = self._table.item(row, 4)
            if status_item:
                txt = status_item.text()
                key = ("finished" if txt.startswith("done") else
                       "error"    if txt.startswith("error") else
                       "stopping" if txt.startswith("stopping") else
                       "running"  if "Fetching" in txt or "Connecting" in txt else "loaded")
                self._color_row(aid, key)

    def _open_results_folder(self) -> None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = str(RESULTS_DIR)
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    # ── Context menu ──────────────────────────────────────────────────────────

    def _context_menu(self, pos) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)
        menu.addAction("Copy Email",    lambda: self._copy_cell(row, 1))
        menu.addAction("Copy Password", lambda: self._copy_cell_raw(row))
        menu.addSeparator()
        menu.addAction("Remove Row",    lambda: self._remove_row(row))
        menu.exec(self._table.mapToGlobal(pos))

    def _copy_cell(self, row: int, col: int) -> None:
        item = self._table.item(row, col)
        if item:
            QApplication.clipboard().setText(item.text())

    def _copy_cell_raw(self, row: int) -> None:
        account_id = self._account_id_for_row(row)
        if account_id is not None:
            from core.account_manager import get_account_password
            pw = get_account_password(account_id) or ""
            QApplication.clipboard().setText(pw)

    def _remove_row(self, row: int) -> None:
        account_id = self._account_id_for_row(row)
        self._worker_manager.stop_account(account_id or -1)
        self._table.removeRow(row)
        self._row_map = {}
        new_accounts = []
        for r in range(self._table.rowCount()):
            num_item = self._table.item(r, 0)
            if num_item:
                num_item.setText(str(r + 1))
            email_item = self._table.item(r, 1)
            if email_item:
                email = email_item.text()
                acct = next((a for a in self._accounts if a["email"] == email), None)
                if acct:
                    self._row_map[acct["id"]] = r
                    new_accounts.append(acct)
        self._accounts = new_accounts
        self._refresh_stats()

    def _account_id_for_row(self, row: int) -> int | None:
        for aid, r in self._row_map.items():
            if r == row:
                return aid
        return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_cell(self, account_id: int, col: int, text: str) -> None:
        row = self._row_map.get(account_id)
        if row is None:
            return
        item = self._table.item(row, col)
        if item:
            item.setText(text)
        else:
            self._table.setItem(row, col, QTableWidgetItem(text))

    def _color_row(self, account_id: int, key: str) -> None:
        row = self._row_map.get(account_id)
        if row is None:
            return
        bg_map = STATUS_BG_DARK if self._dark_mode else STATUS_BG_LIGHT
        color = bg_map.get(key, bg_map["loaded"])
        for col in range(self._table.columnCount()):
            item = self._table.item(row, col)
            if item:
                item.setBackground(color)

    def _refresh_stats(self) -> None:
        loaded  = len(self._accounts)
        running = self._worker_manager.running_count()
        done = sum(
            1 for a in self._accounts
            if a["id"] in self._row_map
            and not self._worker_manager.is_running(a["id"])
            and self._table.item(self._row_map[a["id"]], 4) is not None
            and (self._table.item(self._row_map[a["id"]], 4).text().startswith("done")
                 or self._table.item(self._row_map[a["id"]], 4).text().startswith("error"))
        )
        self._lbl_loaded.setText(f"Loaded: {loaded}")
        self._lbl_running.setText(f"Running: {running}")
        self._lbl_done.setText(f"Done: {done}")
        self._lbl_emails.setText(f"Emails: {self._session_emails:,}")


def _vsep() -> QWidget:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    return sep

"""Activation window shown when no valid license is found."""

from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.license_manager import get_hwid, fetch_and_activate


_STYLE = """
QDialog {
    background-color: #020913;
    color: #e8f4ff;
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
}
QLabel {
    background: transparent;
    color: #e8f4ff;
}
QLabel#title {
    font-size: 28px;
    font-weight: 900;
    letter-spacing: 8px;
    color: #0defa8;
}
QLabel#subtitle {
    font-size: 10px;
    letter-spacing: 3px;
    color: #6b8faa;
    text-transform: uppercase;
}
QLabel#section {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2.5px;
    color: #6b8faa;
    text-transform: uppercase;
}
QLabel#status_ok  { color: #0defa8; font-size: 12px; font-weight: 500; }
QLabel#status_err { color: #ff5e6c; font-size: 12px; font-weight: 500; }
QLabel#status_inf { color: #6b8faa; font-size: 12px; font-weight: 500; }

QLineEdit#hwid_field {
    background-color: rgba(2, 9, 19, 0.75);
    border: 1px solid rgba(13, 239, 168, 0.18);
    border-radius: 8px;
    color: #0defa8;
    font-family: "Courier New", "SF Mono", monospace;
    font-size: 10px;
    letter-spacing: 0.5px;
    padding: 10px 12px;
}
QLineEdit#key_field {
    background-color: rgba(2, 9, 19, 0.75);
    border: 1px solid rgba(13, 239, 168, 0.18);
    border-radius: 8px;
    color: #e8f4ff;
    font-family: "Courier New", "SF Mono", monospace;
    font-size: 13px;
    letter-spacing: 1.5px;
    padding: 11px 14px;
}
QLineEdit#key_field:focus {
    border-color: rgba(13, 239, 168, 0.45);
    background-color: rgba(2, 9, 19, 0.92);
}
QPushButton#copy_btn {
    background-color: rgba(13, 239, 168, 0.10);
    border: 1px solid rgba(13, 239, 168, 0.22);
    border-radius: 6px;
    color: #0defa8;
    font-size: 10px;
    font-weight: 700;
    padding: 6px 14px;
    letter-spacing: 0.5px;
}
QPushButton#copy_btn:hover {
    background-color: rgba(13, 239, 168, 0.20);
    border-color: rgba(13, 239, 168, 0.45);
}
QPushButton#activate_btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0defa8, stop:1 #0ab87e);
    border: none;
    border-radius: 8px;
    color: #020913;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2.5px;
    padding: 13px;
    text-transform: uppercase;
}
QPushButton#activate_btn:hover { background: #0defa8; }
QPushButton#activate_btn:disabled { background: #1a3330; color: #3a6660; }

QFrame#rule {
    color: rgba(13, 239, 168, 0.15);
    border: none;
    border-top: 1px solid rgba(13, 239, 168, 0.15);
    max-height: 1px;
}
QFrame#info_box {
    background-color: rgba(8, 18, 34, 0.75);
    border: 1px solid rgba(13, 239, 168, 0.11);
    border-radius: 8px;
}
"""


class _WorkerSignals(QObject):
    done = pyqtSignal(dict)


class ActivateWindow(QDialog):

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("EMS Mail Fetcher — Activation")
        self.setFixedSize(440, 530)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(_STYLE)
        self._hwid = get_hwid()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 28, 30, 24)
        root.setSpacing(0)

        # ── Logo ────────────────────────────────────────────────────────────
        bolt = QLabel("⚡")
        bolt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bolt.setStyleSheet("font-size: 28px; background: transparent;")
        root.addWidget(bolt)

        title = QLabel("EMS")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        sub = QLabel("Mail Fetcher  —  License Activation")
        sub.setObjectName("subtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(sub)

        root.addSpacing(16)
        root.addWidget(self._rule())
        root.addSpacing(16)

        # ── HWID ─────────────────────────────────────────────────────────────
        lbl_hwid = QLabel("Hardware ID (HWID)")
        lbl_hwid.setObjectName("section")
        root.addWidget(lbl_hwid)
        root.addSpacing(6)

        hwid_row = QHBoxLayout()
        hwid_row.setSpacing(8)

        self._hwid_field = QLineEdit(self._hwid)
        self._hwid_field.setObjectName("hwid_field")
        self._hwid_field.setReadOnly(True)
        hwid_row.addWidget(self._hwid_field)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setObjectName("copy_btn")
        self._copy_btn.setFixedWidth(60)
        self._copy_btn.clicked.connect(self._copy_hwid)
        hwid_row.addWidget(self._copy_btn)
        root.addLayout(hwid_row)

        root.addSpacing(16)

        # ── Key input ────────────────────────────────────────────────────────
        lbl_key = QLabel("License Key")
        lbl_key.setObjectName("section")
        root.addWidget(lbl_key)
        root.addSpacing(6)

        self._key_field = QLineEdit()
        self._key_field.setObjectName("key_field")
        self._key_field.setPlaceholderText("EMF-XXXX-XXXX-XXXX-XXXX")
        self._key_field.returnPressed.connect(self._activate)
        root.addWidget(self._key_field)

        root.addSpacing(12)

        self._activate_btn = QPushButton("ACTIVATE LICENSE")
        self._activate_btn.setObjectName("activate_btn")
        self._activate_btn.clicked.connect(self._activate)
        root.addWidget(self._activate_btn)

        root.addSpacing(8)

        self._status = QLabel("")
        self._status.setObjectName("status_inf")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        root.addSpacing(14)
        root.addWidget(self._rule())
        root.addSpacing(12)

        # ── Instructions ─────────────────────────────────────────────────────
        info_frame = QFrame()
        info_frame.setObjectName("info_box")
        info_lay = QVBoxLayout(info_frame)
        info_lay.setContentsMargins(14, 12, 14, 12)
        info_lay.setSpacing(5)

        head = QLabel("📲  Need a License?")
        head.setObjectName("section")
        info_lay.addWidget(head)

        steps = [
            ("1.", "Copy your HWID above"),
            ("2.", 'Open Telegram → <a href="https://t.me/emsmailerbot" '
                   'style="color:#0defa8;text-decoration:none;font-weight:700;">'
                   '@emsmailerbot</a>'),
            ("3.", "Submit HWID, enter your name &amp; pay"),
            ("4.", "Enter the key you receive above"),
        ]
        for n, text in steps:
            row = QHBoxLayout()
            row.setSpacing(8)
            num = QLabel(n)
            num.setStyleSheet("color: #0defa8; font-weight: 700; font-size: 11px; background: transparent;")
            num.setFixedWidth(16)
            txt = QLabel(text)
            txt.setOpenExternalLinks(True)
            txt.setTextFormat(Qt.TextFormat.RichText)
            txt.setStyleSheet("color: #a8bdd4; font-size: 12px; background: transparent;")
            row.addWidget(num)
            row.addWidget(txt)
            row.addStretch()
            info_lay.addLayout(row)

        sep = QFrame()
        sep.setObjectName("rule")
        info_lay.addWidget(sep)

        support = QLabel(
            '💬 Support: <a href="https://t.me/retiredems" '
            'style="color:#0defa8;text-decoration:none;font-weight:700;">'
            '@retiredems</a>'
        )
        support.setOpenExternalLinks(True)
        support.setTextFormat(Qt.TextFormat.RichText)
        support.setStyleSheet("color: #a8bdd4; font-size: 12px; background: transparent;")
        info_lay.addWidget(support)

        root.addWidget(info_frame)

    def _rule(self) -> QFrame:
        f = QFrame()
        f.setObjectName("rule")
        f.setFrameShape(QFrame.Shape.HLine)
        return f

    def _copy_hwid(self) -> None:
        QApplication.clipboard().setText(self._hwid)
        self._copy_btn.setText("✓ Copied")
        self._copy_btn.setStyleSheet(
            "background-color: rgba(13,239,168,0.22); border: 1px solid #0defa8;"
            "border-radius: 6px; color: #0defa8; font-size: 10px; font-weight: 700; padding: 6px 14px;"
        )
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2200, lambda: (
            self._copy_btn.setText("Copy"),
            self._copy_btn.setStyleSheet(""),
        ))

    def _activate(self) -> None:
        key = self._key_field.text().strip().upper()
        if not key:
            self._set_status("Enter your license key to continue", "err")
            return

        self._activate_btn.setEnabled(False)
        self._activate_btn.setText("VERIFYING…")
        self._set_status("Contacting license server…", "inf")

        signals = _WorkerSignals()
        signals.done.connect(self._on_result)

        def _run():
            result = fetch_and_activate(key)
            signals.done.emit(result)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def _on_result(self, result: dict) -> None:
        self._activate_btn.setText("ACTIVATE LICENSE")
        if result.get("success"):
            self._activate_btn.setEnabled(False)
            self._key_field.setEnabled(False)
            name = result.get("name", "User")
            self._set_status(
                f"✓  Activated for {name}!  Close this window and relaunch EMS Mail Fetcher.",
                "ok",
            )
        else:
            self._activate_btn.setEnabled(True)
            self._set_status("✕  " + (result.get("message") or "Activation failed"), "err")

    def _set_status(self, text: str, kind: str) -> None:
        self._status.setText(text)
        self._status.setObjectName(f"status_{kind}")
        self._status.setStyleSheet(
            {"ok": "color: #0defa8;", "err": "color: #ff5e6c;", "inf": "color: #6b8faa;"}.get(kind, "")
            + " font-size: 12px; font-weight: 500; background: transparent;"
        )

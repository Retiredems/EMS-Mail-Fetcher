"""Add / Edit account dialog — auto-detects server from email domain."""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)

PROTOCOLS = ["IMAP", "POP3", "GMAIL_OAUTH", "OUTLOOK_OAUTH", "EXCHANGE"]


class TestConnectionThread(QThread):
    result = pyqtSignal(bool, str)

    def __init__(self, account_data: dict) -> None:
        super().__init__()
        self._data = account_data

    def run(self) -> None:
        from core.connector import test_connection
        ok, msg = test_connection(self._data)
        self.result.emit(ok, msg)


class AccountDialog(QDialog):
    account_saved = pyqtSignal()

    def __init__(self, parent=None, account_id: Optional[int] = None) -> None:
        super().__init__(parent)
        self.account_id = account_id
        self.setWindowTitle("Add Account" if account_id is None else "Edit Account")
        self.setMinimumWidth(460)
        self._detect_timer = QTimer()
        self._detect_timer.setSingleShot(True)
        self._detect_timer.timeout.connect(self._auto_detect)
        self._build_ui()
        if account_id:
            self._load_existing()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ── Credentials ───────────────────────────────────────────────────────
        cred_box = QGroupBox("Account Credentials")
        cred_lay = QFormLayout(cred_box)

        self._email_edit = QLineEdit()
        self._email_edit.setPlaceholderText("you@gmail.com")
        self._email_edit.textChanged.connect(self._on_email_changed)
        cred_lay.addRow("Email Address:", self._email_edit)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Password or app password")
        cred_lay.addRow("Password:", self._password_edit)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Optional display name")
        cred_lay.addRow("Display Name:", self._name_edit)

        root.addWidget(cred_box)

        # ── Auto-detected info banner ─────────────────────────────────────────
        self._detected_label = QLabel("")
        self._detected_label.setTextFormat(Qt.TextFormat.RichText)
        self._detected_label.setWordWrap(True)
        self._detected_label.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._detected_label)

        # ── OAuth button (shown only for OAuth providers) ─────────────────────
        self._oauth_widget = QWidget()
        oauth_lay = QHBoxLayout(self._oauth_widget)
        oauth_lay.setContentsMargins(0, 0, 0, 0)
        self._oauth_btn = QPushButton("Sign in with Google / Microsoft")
        self._oauth_btn.clicked.connect(self._on_oauth)
        oauth_lay.addWidget(self._oauth_btn)
        oauth_lay.addStretch()
        self._oauth_widget.setVisible(False)
        root.addWidget(self._oauth_widget)

        # ── Advanced / override (collapsed by default) ────────────────────────
        self._advanced_box = QGroupBox("Advanced (override auto-detected settings)")
        self._advanced_box.setCheckable(True)
        self._advanced_box.setChecked(False)
        adv_lay = QFormLayout(self._advanced_box)

        self._protocol_combo = QComboBox()
        self._protocol_combo.addItems(PROTOCOLS)
        adv_lay.addRow("Protocol:", self._protocol_combo)

        self._server_edit = QLineEdit()
        adv_lay.addRow("Server:", self._server_edit)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(993)
        adv_lay.addRow("Port:", self._port_spin)

        self._ssl_check = QCheckBox("Use SSL/TLS")
        self._ssl_check.setChecked(True)
        adv_lay.addRow("", self._ssl_check)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("Leave blank to use email address")
        adv_lay.addRow("Username:", self._username_edit)

        root.addWidget(self._advanced_box)

        # ── Test + Save row ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setProperty("secondary", "true")
        self._test_btn.clicked.connect(self._on_test)
        self._test_label = QLabel("")
        self._test_label.setTextFormat(Qt.TextFormat.RichText)
        self._test_label.setWordWrap(True)
        btn_row.addWidget(self._test_btn)
        btn_row.addWidget(self._test_label, 1)
        root.addLayout(btn_row)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_btn = QPushButton("Save Account")
        self._save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("secondary", "true")
        cancel_btn.clicked.connect(self.reject)
        save_row.addWidget(self._save_btn)
        save_row.addWidget(cancel_btn)
        root.addLayout(save_row)

    # ── Auto-detection ────────────────────────────────────────────────────────

    def _on_email_changed(self, text: str) -> None:
        self._detected_label.setText("")
        if "@" in text and "." in text.split("@", 1)[1]:
            self._detect_timer.start(400)

    def _auto_detect(self) -> None:
        email = self._email_edit.text().strip()
        if "@" not in email:
            return

        from core.account_manager import lookup_domain_preset
        preset = lookup_domain_preset(email)
        domain = email.split("@", 1)[1]

        if not preset:
            self._detected_label.setText(
                f"<span style='color:#f9e2af'>⚠ No preset found for <b>{domain}</b> — "
                f"expand Advanced to enter server settings manually.</span>"
            )
            return

        imap = preset.get("imap", {})
        pop3 = preset.get("pop3", {})
        oauth = preset.get("oauth", "")
        is_oauth_only = bool(oauth) and not imap

        # Fill advanced fields silently
        if imap:
            self._server_edit.setText(imap.get("server", ""))
            self._port_spin.setValue(imap.get("port", 993))
            self._ssl_check.setChecked(imap.get("ssl", True))
            proto = "IMAP"
            if oauth == "gmail":
                proto = "GMAIL_OAUTH"
            elif oauth == "microsoft":
                proto = "OUTLOOK_OAUTH"
            idx = self._protocol_combo.findText(proto)
            if idx >= 0:
                self._protocol_combo.setCurrentIndex(idx)

        # Show OAuth button for OAuth providers
        self._oauth_widget.setVisible(bool(oauth))
        self._password_edit.setEnabled(not is_oauth_only)

        # Build info text
        if is_oauth_only:
            info = (
                f"<span style='color:#89dceb'>🔍 Detected: <b>{domain}</b> — "
                f"OAuth only. Click <b>Sign in</b> below.</span>"
            )
        elif imap:
            note = preset.get("_note", "")
            note_html = f" &nbsp;<i>{note}</i>" if note else ""
            info = (
                f"<span style='color:#a6e3a1'>✔ Detected: <b>{domain}</b> → "
                f"{imap['server']}:{imap.get('port', 993)} "
                f"({'SSL' if imap.get('ssl') else 'STARTTLS'})"
                f"{note_html}</span>"
            )
        else:
            info = f"<span style='color:#f9e2af'>⚠ Domain known but no IMAP settings — check Advanced.</span>"

        self._detected_label.setText(info)

    # ── OAuth ─────────────────────────────────────────────────────────────────

    def _on_oauth(self) -> None:
        email = self._email_edit.text().strip()
        if not email:
            QMessageBox.warning(self, "Email Required", "Enter your email address first.")
            return
        try:
            account_id = self._ensure_account_saved()
            proto = self._protocol_combo.currentText()
            if proto == "GMAIL_OAUTH":
                from core.gmail_oauth import run_oauth_flow
                run_oauth_flow(account_id)
            else:
                from core.outlook_oauth import run_oauth_flow
                run_oauth_flow(account_id)
            QMessageBox.information(self, "OAuth Complete", "Successfully authorised.")
            self.account_saved.emit()
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "OAuth Error", str(exc))

    def _ensure_account_saved(self) -> int:
        """Save account (or return existing ID) so OAuth can attach to it."""
        from db.database import get_session
        from db import repository as repo
        from core.account_manager import add_account
        email = self._email_edit.text().strip()
        with get_session() as session:
            existing = repo.get_account_by_email(session, email)
            if existing:
                return existing.id
        return add_account(
            email=email,
            protocol=self._protocol_combo.currentText(),
            display_name=self._name_edit.text().strip() or email,
            server=self._server_edit.text().strip(),
            port=self._port_spin.value(),
            use_ssl=self._ssl_check.isChecked(),
            username=self._username_edit.text().strip() or email,
        )

    # ── Test connection ───────────────────────────────────────────────────────

    def _on_test(self) -> None:
        self._test_label.setText("Testing…")
        self._test_btn.setEnabled(False)
        self._thread = TestConnectionThread(self._collect_data())
        self._thread.result.connect(self._on_test_result)
        self._thread.start()

    def _on_test_result(self, ok: bool, msg: str) -> None:
        self._test_btn.setEnabled(True)
        if ok:
            self._test_label.setText(f"<span style='color:#a6e3a1'>✔ {msg}</span>")
        else:
            self._test_label.setText(f"<span style='color:#f38ba8'>✘ {msg}</span>")

    # ── Save ──────────────────────────────────────────────────────────────────

    def _collect_data(self) -> dict:
        email = self._email_edit.text().strip()
        return {
            "id": self.account_id or -1,
            "email": email,
            "display_name": self._name_edit.text().strip() or email,
            "protocol": self._protocol_combo.currentText(),
            "server": self._server_edit.text().strip(),
            "port": self._port_spin.value(),
            "use_ssl": self._ssl_check.isChecked(),
            "username": self._username_edit.text().strip() or email,
            "password": self._password_edit.text(),
        }

    def _on_save(self) -> None:
        data = self._collect_data()
        if not data["email"] or "@" not in data["email"]:
            QMessageBox.warning(self, "Validation", "Enter a valid email address.")
            return

        try:
            if self.account_id is None:
                from core.account_manager import add_account
                add_account(
                    email=data["email"],
                    protocol=data["protocol"],
                    display_name=data["display_name"],
                    server=data["server"],
                    port=data["port"],
                    use_ssl=data["use_ssl"],
                    username=data["username"],
                    password=data["password"],
                )
            else:
                from db.database import get_session
                from db import repository as repo
                from core.account_manager import encrypt
                with get_session() as session:
                    account = repo.get_account_by_id(session, self.account_id)
                    updates: dict = {
                        "display_name": data["display_name"],
                        "protocol": data["protocol"],
                        "server": data["server"],
                        "port": data["port"],
                        "use_ssl": data["use_ssl"],
                        "username": data["username"],
                    }
                    if data["password"]:
                        updates["encrypted_password"] = encrypt(data["password"])
                    repo.update_account(session, account, **updates)

            self.account_saved.emit()
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _load_existing(self) -> None:
        from db.database import get_session
        from db import repository as repo
        with get_session() as session:
            a = repo.get_account_by_id(session, self.account_id)
            if not a:
                return
            self._email_edit.setText(a.email)
            self._name_edit.setText(a.display_name or "")
            self._server_edit.setText(a.server or "")
            self._port_spin.setValue(a.port or 993)
            self._ssl_check.setChecked(a.use_ssl)
            self._username_edit.setText(a.username or "")
            idx = self._protocol_combo.findText(a.protocol or "IMAP")
            if idx >= 0:
                self._protocol_combo.setCurrentIndex(idx)
        self._advanced_box.setChecked(True)

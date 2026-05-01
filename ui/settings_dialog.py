"""Application settings dialog."""

from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

SETTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "settings.json"


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _defaults()


def save_settings(data: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _defaults() -> dict:
    from config.settings import ARCHIVE_DIR, EXPORT_DIR
    return {
        "archive_dir": str(ARCHIVE_DIR),
        "export_dir": str(EXPORT_DIR),
        "thread_count": 3,
        "skip_trash": True,
        "skip_spam": True,
        "skip_drafts": False,
        "save_eml": True,
        "skip_duplicates": True,
        "theme": "dark",
        "proxy": {
            "enabled": False,
            "host": "",
            "port": 1080,
            "username": "",
            "password": "",
        },
    }


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(460)
        self._settings = load_settings()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ── General ───────────────────────────────────────────────────────────
        general = QGroupBox("General")
        gen_lay = QFormLayout(general)

        self._archive_edit = QLineEdit(self._settings.get("archive_dir", ""))
        browse_archive = QPushButton("Browse…")
        browse_archive.setProperty("secondary", "true")
        browse_archive.clicked.connect(lambda: self._browse(self._archive_edit))
        arch_row = QHBoxLayout()
        arch_row.addWidget(self._archive_edit)
        arch_row.addWidget(browse_archive)
        gen_lay.addRow("Archive directory:", arch_row)

        self._export_edit = QLineEdit(self._settings.get("export_dir", ""))
        browse_export = QPushButton("Browse…")
        browse_export.setProperty("secondary", "true")
        browse_export.clicked.connect(lambda: self._browse(self._export_edit))
        exp_row = QHBoxLayout()
        exp_row.addWidget(self._export_edit)
        exp_row.addWidget(browse_export)
        gen_lay.addRow("Export directory:", exp_row)

        self._thread_spin = QSpinBox()
        self._thread_spin.setRange(1, 10)
        self._thread_spin.setValue(self._settings.get("thread_count", 3))
        gen_lay.addRow("Worker threads:", self._thread_spin)
        root.addWidget(general)

        # ── Sync options ──────────────────────────────────────────────────────
        sync = QGroupBox("Sync Defaults")
        sync_lay = QFormLayout(sync)

        self._save_eml_check = QCheckBox("Save .eml files to disk")
        self._save_eml_check.setChecked(self._settings.get("save_eml", True))
        sync_lay.addRow("", self._save_eml_check)

        self._skip_dup_check = QCheckBox("Skip duplicate emails (by UID / Message-ID)")
        self._skip_dup_check.setChecked(self._settings.get("skip_duplicates", True))
        sync_lay.addRow("", self._skip_dup_check)

        self._skip_trash_check = QCheckBox("Exclude Trash / Deleted")
        self._skip_trash_check.setChecked(self._settings.get("skip_trash", True))
        sync_lay.addRow("", self._skip_trash_check)

        self._skip_spam_check = QCheckBox("Exclude Spam / Junk")
        self._skip_spam_check.setChecked(self._settings.get("skip_spam", True))
        sync_lay.addRow("", self._skip_spam_check)

        self._skip_drafts_check = QCheckBox("Exclude Drafts")
        self._skip_drafts_check.setChecked(self._settings.get("skip_drafts", False))
        sync_lay.addRow("", self._skip_drafts_check)

        root.addWidget(sync)

        # ── Security ──────────────────────────────────────────────────────────
        sec = QGroupBox("Security")
        sec_lay = QFormLayout(sec)
        clear_btn = QPushButton("Clear All Stored Credentials")
        clear_btn.setProperty("secondary", "true")
        clear_btn.clicked.connect(self._clear_credentials)
        sec_lay.addRow("", clear_btn)
        root.addWidget(sec)

        # ── Buttons ───────────────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _browse(self, edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Directory", edit.text())
        if path:
            edit.setText(path)

    def _clear_credentials(self) -> None:
        reply = QMessageBox.question(
            self, "Confirm",
            "This will remove all stored passwords and OAuth tokens.\n"
            "You will need to re-enter credentials for all accounts.\nContinue?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            from db.database import get_session
            from db import repository as repo
            with get_session() as session:
                for a in repo.get_all_accounts(session):
                    repo.update_account(session, a, encrypted_password=None, oauth_token_json=None)
            QMessageBox.information(self, "Done", "All credentials cleared.")

    def _on_save(self) -> None:
        # Load existing settings first so keys managed elsewhere (proxy, theme,
        # proxy_list, proxy_file) are preserved and not silently wiped.
        data = load_settings()
        data.update({
            "archive_dir": self._archive_edit.text().strip(),
            "export_dir": self._export_edit.text().strip(),
            "thread_count": self._thread_spin.value(),
            "save_eml": self._save_eml_check.isChecked(),
            "skip_duplicates": self._skip_dup_check.isChecked(),
            "skip_trash": self._skip_trash_check.isChecked(),
            "skip_spam": self._skip_spam_check.isChecked(),
            "skip_drafts": self._skip_drafts_check.isChecked(),
        })
        save_settings(data)
        self.accept()

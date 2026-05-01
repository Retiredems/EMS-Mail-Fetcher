"""Emails tab: browse, search, preview, and export archived emails."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)

COLUMNS = ["Subject", "From", "Date", "Folder", "Size (KB)", "Account"]


class EmailsPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._emails: list = []
        self._build_ui()
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Toolbar ───────────────────────────────────────────────────────────
        bar = QHBoxLayout()

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search by subject…")
        self._search_edit.textChanged.connect(lambda: self._search_timer.start(300))
        bar.addWidget(self._search_edit, 2)

        self._account_filter = QComboBox()
        self._account_filter.addItem("All Accounts", None)
        self._account_filter.currentIndexChanged.connect(self._do_search)
        bar.addWidget(self._account_filter, 1)

        self._total_label = QLabel("0 emails")
        bar.addWidget(self._total_label)
        bar.addStretch()

        btn_export = QPushButton("Export .eml")
        btn_export.setProperty("secondary", "true")
        btn_export.clicked.connect(self._export_eml)
        bar.addWidget(btn_export)

        btn_open = QPushButton("Open in Client")
        btn_open.setProperty("secondary", "true")
        btn_open.clicked.connect(self._open_in_client)
        bar.addWidget(btn_open)

        root.addLayout(bar)

        # ── Splitter: table + preview ─────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.currentItemChanged.connect(self._on_row_selected)
        splitter.addWidget(self._table)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("Select an email above to preview its content…")
        splitter.addWidget(self._preview)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

    def refresh(self) -> None:
        from db.database import get_session
        from db import repository as repo
        with get_session() as session:
            accounts = repo.get_all_accounts(session)
            self._account_filter.blockSignals(True)
            current_id = self._account_filter.currentData()
            self._account_filter.clear()
            self._account_filter.addItem("All Accounts", None)
            for a in accounts:
                self._account_filter.addItem(a.email, a.id)
            for i in range(self._account_filter.count()):
                if self._account_filter.itemData(i) == current_id:
                    self._account_filter.setCurrentIndex(i)
                    break
            self._account_filter.blockSignals(False)
        self._do_search()

    def _do_search(self) -> None:
        search = self._search_edit.text().strip() or None
        account_id = self._account_filter.currentData()

        from db.database import get_session
        from db.models import Email, Folder
        from db import repository as repo
        from sqlalchemy.orm import joinedload
        with get_session() as session:
            if account_id is not None:
                q = session.query(Email).options(joinedload(Email.folder)).filter_by(account_id=account_id)
            else:
                q = session.query(Email).options(joinedload(Email.folder))
            if search:
                q = q.filter(Email.subject.ilike(f"%{search}%"))
            emails = q.order_by(Email.date_sent.desc()).limit(2000).all()
            # Detach-safe: collect folder paths while session is open
            email_rows = [
                {
                    "subject": e.subject,
                    "from_address": e.from_address,
                    "date_sent": e.date_sent,
                    "folder_path": e.folder.full_path if e.folder else "",
                    "raw_size_bytes": e.raw_size_bytes,
                    "account_id": e.account_id,
                    "raw_eml_path": e.raw_eml_path,
                    "_obj": e,
                }
                for e in emails
            ]

        self._emails = email_rows
        self._populate_table(email_rows)
        self._total_label.setText(f"{len(email_rows):,} emails")

    def _populate_table(self, email_rows: list) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for e in email_rows:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(e["subject"] or "(no subject)"))
            self._table.setItem(row, 1, QTableWidgetItem(e["from_address"] or ""))
            self._table.setItem(row, 2, QTableWidgetItem(
                e["date_sent"].strftime("%Y-%m-%d %H:%M") if e["date_sent"] else ""
            ))
            self._table.setItem(row, 3, QTableWidgetItem(e["folder_path"]))
            size_item = QTableWidgetItem()
            size_item.setData(Qt.ItemDataRole.DisplayRole, round(e["raw_size_bytes"] / 1024, 1))
            self._table.setItem(row, 4, size_item)
            self._table.setItem(row, 5, QTableWidgetItem(str(e["account_id"])))
        self._table.setSortingEnabled(True)

    def _on_row_selected(self, current, _previous) -> None:
        if not current:
            return
        row = current.row()
        if row >= len(self._emails):
            return
        self._load_preview(self._emails[row])

    def _load_preview(self, email_row: dict) -> None:
        eml_path = email_row.get("raw_eml_path")
        if not eml_path:
            self._preview.setPlainText("(No .eml file saved for this email)")
            return
        path = Path(eml_path)
        if not path.exists():
            self._preview.setPlainText(f"File not found:\n{path}")
            return
        try:
            import email as email_lib
            import email.policy
            raw = path.read_bytes()
            msg = email_lib.message_from_bytes(raw, policy=email_lib.policy.default)

            lines = [
                f"From:    {msg.get('From', '')}",
                f"To:      {msg.get('To', '')}",
                f"Subject: {msg.get('Subject', '')}",
                f"Date:    {msg.get('Date', '')}",
                "",
            ]

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct == "text/plain":
                        body = part.get_content()
                        break
                if not body:
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            body = part.get_content()
                            break
            else:
                body = msg.get_content()

            self._preview.setPlainText("\n".join(lines) + (body or "(empty body)"))
        except Exception as exc:
            self._preview.setPlainText(f"Preview error: {exc}")

    def _selected_email_objects(self) -> list:
        rows = {idx.row() for idx in self._table.selectedIndexes()}
        if not rows:
            return []
        return [self._emails[r] for r in sorted(rows) if r < len(self._emails)]

    def _export_eml(self) -> None:
        selected = self._selected_email_objects()
        if not selected:
            QMessageBox.information(self, "Export", "Select emails to export first.")
            return
        dest = QFileDialog.getExistingDirectory(self, "Choose Export Directory")
        if not dest:
            return
        try:
            from export.eml_exporter import export_emails_eml
            # Pass file paths directly
            count = 0
            for row in selected:
                eml = row.get("raw_eml_path")
                if eml:
                    import shutil
                    src = Path(eml)
                    if src.exists():
                        shutil.copy2(src, Path(dest) / src.name)
                        count += 1
            QMessageBox.information(self, "Done", f"Exported {count} .eml files to:\n{dest}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    def _open_in_client(self) -> None:
        rows = {idx.row() for idx in self._table.selectedIndexes()}
        if not rows:
            return
        row = min(rows)
        if row >= len(self._emails):
            return
        email_row = self._emails[row]
        eml_path = email_row.get("raw_eml_path")
        if not eml_path or not Path(eml_path).exists():
            QMessageBox.warning(self, "Open", "No .eml file available for this email.")
            return
        path = str(Path(eml_path))
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform == "win32":
                subprocess.Popen(["start", "", path], shell=True)
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            QMessageBox.critical(self, "Open Error", str(exc))

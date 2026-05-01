"""Import accounts from an email:password text file."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

STATUS_COLORS = {
    "added":     "#a6e3a1",
    "duplicate": "#f9e2af",
    "skipped":   "#a6adc8",
    "error":     "#f38ba8",
}


class ImportAccountsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Accounts from File")
        self.setMinimumSize(620, 420)
        self._results: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ── File picker row ───────────────────────────────────────────────────
        info = QLabel(
            "Select a <b>.txt</b> file where each line is: &nbsp;<code>email:password</code><br>"
            "Lines starting with <code>#</code> and blank lines are ignored."
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(info)

        file_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Path to accounts.txt …")
        self._path_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        file_row.addWidget(self._path_edit, 1)
        file_row.addWidget(browse_btn)
        root.addLayout(file_row)

        # ── Preview / results table ───────────────────────────────────────────
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Email", "Status", "Details"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self._table)

        self._summary_label = QLabel("")
        root.addWidget(self._summary_label)

        # ── Buttons ───────────────────────────────────────────────────────────
        self._import_btn = QPushButton("Import")
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self._do_import)

        close_btn = QPushButton("Close")
        close_btn.setProperty("secondary", "true")
        close_btn.clicked.connect(self.accept)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._import_btn)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Account List File", "", "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return
        self._path_edit.setText(path)
        self._preview_file(path)
        self._import_btn.setEnabled(True)

    def _preview_file(self, path: str) -> None:
        """Parse the file and show a dry-run preview in the table."""
        self._table.setRowCount(0)
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        valid = 0
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            row = self._table.rowCount()
            self._table.insertRow(row)
            if ":" in line:
                email = line.split(":", 1)[0].strip()
                self._table.setItem(row, 0, QTableWidgetItem(email))
                self._table.setItem(row, 1, QTableWidgetItem("pending"))
                self._table.setItem(row, 2, QTableWidgetItem("—"))
                valid += 1
            else:
                self._table.setItem(row, 0, QTableWidgetItem(line))
                self._table.setItem(row, 1, QTableWidgetItem("skipped"))
                self._table.setItem(row, 2, QTableWidgetItem("No colon separator"))
        self._summary_label.setText(f"{valid} account(s) ready to import.")

    def _do_import(self) -> None:
        path = self._path_edit.text()
        if not path:
            return

        self._import_btn.setEnabled(False)
        self._import_btn.setText("Importing…")

        from core.account_manager import import_accounts_from_file
        results = import_accounts_from_file(path)
        self._results = results

        self._table.setRowCount(0)
        added = dupes = errors = skipped = 0

        for r in results:
            row = self._table.rowCount()
            self._table.insertRow(row)

            email_item = QTableWidgetItem(r["email"])
            status_item = QTableWidgetItem(r["status"])
            detail_item = QTableWidgetItem(r["message"])

            color = QColor(STATUS_COLORS.get(r["status"], "#cdd6f4"))
            for item in (email_item, status_item, detail_item):
                item.setForeground(color)

            self._table.setItem(row, 0, email_item)
            self._table.setItem(row, 1, status_item)
            self._table.setItem(row, 2, detail_item)

            if r["status"] == "added":       added += 1
            elif r["status"] == "duplicate": dupes += 1
            elif r["status"] == "error":     errors += 1
            else:                            skipped += 1

        self._summary_label.setText(
            f"Done — Added: {added}  |  Duplicates: {dupes}  |  Skipped: {skipped}  |  Errors: {errors}"
        )
        self._import_btn.setText("Import Again")
        self._import_btn.setEnabled(True)

    def imported_any(self) -> bool:
        return any(r["status"] == "added" for r in self._results)

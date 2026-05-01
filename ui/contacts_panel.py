"""Contacts tab: searchable, sortable, exportable contacts table."""

from __future__ import annotations

import logging
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)

COLUMNS = ["Email Address", "Display Name", "Occurrences", "First Seen", "Last Seen", "Account"]


class ContactsPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._contacts: list = []
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
        self._search_edit.setPlaceholderText("Search by email or name…")
        self._search_edit.textChanged.connect(lambda: self._search_timer.start(300))
        bar.addWidget(self._search_edit, 2)

        self._account_filter = QComboBox()
        self._account_filter.addItem("All Accounts", None)
        self._account_filter.currentIndexChanged.connect(self._do_search)
        bar.addWidget(self._account_filter, 1)

        self._total_label = QLabel("0 contacts")
        bar.addWidget(self._total_label)

        bar.addStretch()

        btn_csv = QPushButton("Export CSV")
        btn_csv.setProperty("secondary", "true")
        btn_csv.clicked.connect(lambda: self._export("csv"))
        bar.addWidget(btn_csv)

        btn_vcf = QPushButton("Export vCard")
        btn_vcf.setProperty("secondary", "true")
        btn_vcf.clicked.connect(lambda: self._export("vcf"))
        bar.addWidget(btn_vcf)

        btn_xlsx = QPushButton("Export Excel")
        btn_xlsx.setProperty("secondary", "true")
        btn_xlsx.clicked.connect(lambda: self._export("xlsx"))
        bar.addWidget(btn_xlsx)

        root.addLayout(bar)

        # ── Table ─────────────────────────────────────────────────────────────
        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        root.addWidget(self._table)

    def refresh(self) -> None:
        """Reload contacts from DB and refresh account filter."""
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
            # Restore selection
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
        from db import repository as repo
        with get_session() as session:
            if account_id:
                contacts = repo.get_contacts_for_account(session, account_id, search=search)
            else:
                contacts = repo.get_all_contacts(session, search=search)

        self._contacts = contacts
        self._populate_table(contacts)
        self._total_label.setText(f"{len(contacts):,} contacts")

    def _populate_table(self, contacts: list) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for c in contacts:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(c.email_address))
            self._table.setItem(row, 1, QTableWidgetItem(c.display_name or ""))
            occ_item = QTableWidgetItem()
            occ_item.setData(Qt.ItemDataRole.DisplayRole, c.occurrence_count)
            self._table.setItem(row, 2, occ_item)
            self._table.setItem(row, 3, QTableWidgetItem(
                c.first_seen_at.strftime("%Y-%m-%d") if c.first_seen_at else ""
            ))
            self._table.setItem(row, 4, QTableWidgetItem(
                c.last_seen_at.strftime("%Y-%m-%d") if c.last_seen_at else ""
            ))
            self._table.setItem(row, 5, QTableWidgetItem(str(c.account_id)))
        self._table.setSortingEnabled(True)

    def _selected_contacts(self) -> list:
        rows = {idx.row() for idx in self._table.selectedIndexes()}
        if not rows:
            return self._contacts
        return [self._contacts[r] for r in sorted(rows) if r < len(self._contacts)]

    def _export(self, fmt: str) -> None:
        contacts = self._selected_contacts()
        if not contacts:
            QMessageBox.information(self, "Export", "No contacts to export.")
            return

        filters = {
            "csv":  ("CSV Files (*.csv)", ".csv"),
            "vcf":  ("vCard Files (*.vcf)", ".vcf"),
            "xlsx": ("Excel Files (*.xlsx)", ".xlsx"),
        }
        filter_str, ext = filters[fmt]
        path, _ = QFileDialog.getSaveFileName(self, "Export Contacts", f"contacts{ext}", filter_str)
        if not path:
            return

        try:
            out = Path(path)
            if fmt == "csv":
                from export.csv_exporter import export_contacts_csv
                n = export_contacts_csv(contacts, out)
            elif fmt == "vcf":
                from export.vcard_exporter import export_contacts_vcard
                n = export_contacts_vcard(contacts, out)
            else:
                from export.excel_exporter import export_contacts_excel
                n = export_contacts_excel(contacts, out)
            QMessageBox.information(self, "Export Complete", f"Exported {n:,} contacts to:\n{out}")
        except Exception as exc:
            log.exception("Export failed")
            QMessageBox.critical(self, "Export Error", str(exc))

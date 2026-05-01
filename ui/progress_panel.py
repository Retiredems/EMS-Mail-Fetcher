"""Progress tab: per-account fetch status table."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

COLUMNS = [
    "#", "Account", "Protocol", "Server", "Status",
    "Folders", "Emails", "Contacts", "Speed (e/min)",
]

STATUS_BG = {
    "Done":        QColor("#1e3a2f"),
    "Error":       QColor("#3a1e1e"),
    "Paused":      QColor("#3a331e"),
    "Connecting":  QColor("#1e2a3a"),
    "Fetching":    QColor("#1e2a3a"),
    "Idle":        QColor("#1e1e2e"),
}


class ProgressPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._label = QLabel("Fetch Progress")
        self._label.setProperty("class", "heading")
        layout.addWidget(self._label)

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        # account_id → row index
        self._row_map: dict[int, int] = {}
        self._next_row = 0

    def add_account_row(self, account_id: int, email: str, protocol: str, server: str) -> None:
        if account_id in self._row_map:
            return
        row = self._next_row
        self._next_row += 1
        self._row_map[account_id] = row
        self._table.insertRow(row)

        def cell(text: str) -> QTableWidgetItem:
            item = QTableWidgetItem(str(text))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            return item

        self._table.setItem(row, 0, cell(str(row + 1)))
        self._table.setItem(row, 1, QTableWidgetItem(email))
        self._table.setItem(row, 2, cell(protocol))
        self._table.setItem(row, 3, QTableWidgetItem(server or ""))
        self._table.setItem(row, 4, cell("Idle"))
        self._table.setItem(row, 5, cell("—"))
        self._table.setItem(row, 6, cell("—"))
        self._table.setItem(row, 7, cell("0"))
        self._table.setItem(row, 8, cell("—"))

    def set_status(self, account_id: int, status: str) -> None:
        row = self._row_map.get(account_id)
        if row is None:
            return
        item = self._table.item(row, 4)
        if item:
            # Truncate long status strings
            display = status[:40] + "…" if len(status) > 40 else status
            item.setText(display)
            item.setToolTip(status)
        # Colour entire row
        status_key = status.split(":")[0].strip()
        bg = STATUS_BG.get(status_key, STATUS_BG["Idle"])
        for col in range(self._table.columnCount()):
            cell = self._table.item(row, col)
            if cell:
                cell.setBackground(QBrush(bg))

    def set_progress(
        self,
        account_id: int,
        folders_done: int,
        folders_total: int,
        emails_done: int,
        emails_total: int,
    ) -> None:
        row = self._row_map.get(account_id)
        if row is None:
            return
        folders_text = f"{folders_done}/{folders_total}" if folders_total else str(folders_done)
        emails_text = f"{emails_done:,}" + (f"/{emails_total:,}" if emails_total else "")
        self._set_cell(row, 5, folders_text)
        self._set_cell(row, 6, emails_text)

    def set_contacts(self, account_id: int, count: int) -> None:
        row = self._row_map.get(account_id)
        if row is None:
            return
        self._set_cell(row, 7, f"{count:,}")

    def set_speed(self, account_id: int, speed: float) -> None:
        row = self._row_map.get(account_id)
        if row is None:
            return
        self._set_cell(row, 8, f"{speed:.0f}")

    def _set_cell(self, row: int, col: int, text: str) -> None:
        item = self._table.item(row, col)
        if item:
            item.setText(text)
        else:
            new_item = QTableWidgetItem(text)
            new_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, col, new_item)

    def remove_account_row(self, account_id: int) -> None:
        row = self._row_map.pop(account_id, None)
        if row is not None:
            self._table.removeRow(row)
            # Fix row indices
            self._row_map = {
                aid: r - (1 if r > row else 0)
                for aid, r in self._row_map.items()
            }
            self._next_row -= 1

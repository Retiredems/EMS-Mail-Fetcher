"""Left sidebar: account list with colour-coded status dots."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

STATUS_COLORS = {
    "idle":     "#a6adc8",
    "running":  "#89dceb",
    "paused":   "#f9e2af",
    "done":     "#a6e3a1",
    "error":    "#f38ba8",
}

DOT = "●"  # ●


class AccountsPanel(QWidget):
    account_selected = pyqtSignal(int)  # emits account_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._id_map: dict[int, QListWidgetItem] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Accounts")
        header.setProperty("class", "heading")
        header.setContentsMargins(10, 10, 10, 6)
        layout.addWidget(header)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(False)
        self._list.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list)

    def _on_item_changed(self, current: QListWidgetItem, _previous) -> None:
        if current:
            account_id = current.data(Qt.ItemDataRole.UserRole)
            self.account_selected.emit(account_id)

    def add_account(self, account_id: int, email: str, status: str = "idle") -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, account_id)
        self._id_map[account_id] = item
        self._update_item(item, email, status)
        self._list.addItem(item)

    def remove_account(self, account_id: int) -> None:
        item = self._id_map.pop(account_id, None)
        if item:
            row = self._list.row(item)
            self._list.takeItem(row)

    def set_status(self, account_id: int, status: str) -> None:
        item = self._id_map.get(account_id)
        if item:
            email = item.data(Qt.ItemDataRole.UserRole + 1)
            self._update_item(item, email, status)

    def _update_item(self, item: QListWidgetItem, email: str, status: str) -> None:
        color = STATUS_COLORS.get(status, STATUS_COLORS["idle"])
        item.setText(f"{DOT}  {email}")
        item.setForeground(QColor(color))
        item.setData(Qt.ItemDataRole.UserRole + 1, email)
        item.setToolTip(f"Status: {status}")

    def refresh_from_db(self) -> None:
        from db.database import get_session
        from db import repository as repo
        with get_session() as session:
            accounts = repo.get_all_accounts(session)
            existing_ids = {a.id for a in accounts}

        # Remove stale
        for aid in list(self._id_map.keys()):
            if aid not in existing_ids:
                self.remove_account(aid)

        # Add/update
        with get_session() as session:
            for a in repo.get_all_accounts(session):
                if a.id in self._id_map:
                    self.set_status(a.id, a.status)
                else:
                    self.add_account(a.id, a.email, a.status)

    def selected_account_id(self) -> int | None:
        item = self._list.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

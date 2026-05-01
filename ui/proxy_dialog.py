"""Proxy configuration dialog — supports manual SOCKS5 entry and bulk file loading."""

from __future__ import annotations

import re
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
    QSpinBox,
    QVBoxLayout,
    QPushButton,
)

from ui.settings_dialog import load_settings, save_settings


def _parse_proxy_line(line: str) -> dict | None:
    """Parse one proxy line into a proxy dict. Returns None on bad input."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # socks5://user:pass@host:port  or  socks5://host:port
    m = re.match(
        r"^(?:socks5://)"
        r"(?:([^:@]+):([^@]*)@)?"   # optional user:pass@
        r"([^:]+):(\d+)$",
        line, re.IGNORECASE,
    )
    if m:
        user, pw, host, port = m.groups()
        return {
            "enabled": True,
            "host": host.strip(),
            "port": int(port),
            "username": user or "",
            "password": pw or "",
        }

    # host:port:user:pass  or  host:port
    parts = line.split(":")
    if len(parts) >= 2 and parts[1].isdigit():
        return {
            "enabled": True,
            "host": parts[0].strip(),
            "port": int(parts[1]),
            "username": parts[2].strip() if len(parts) > 2 else "",
            "password": parts[3].strip() if len(parts) > 3 else "",
        }

    return None


def parse_proxy_file(path: str) -> list[dict]:
    """Return a list of proxy dicts parsed from a text file (one proxy per line)."""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        result = []
        for line in lines:
            p = _parse_proxy_line(line)
            if p:
                result.append(p)
        return result
    except Exception:
        return []


class ProxyDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Proxy Settings (SOCKS5)")
        self.setMinimumWidth(420)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # ── Manual single proxy ───────────────────────────────────────────────
        box = QGroupBox("Manual SOCKS5 Proxy")
        form = QFormLayout(box)

        self._enabled = QCheckBox("Enable (used when no proxy file is loaded)")
        form.addRow("", self._enabled)

        self._host = QLineEdit()
        self._host.setPlaceholderText("127.0.0.1")
        form.addRow("Host:", self._host)

        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(1080)
        form.addRow("Port:", self._port)

        self._user = QLineEdit()
        self._user.setPlaceholderText("Optional username")
        form.addRow("Username:", self._user)

        self._pass = QLineEdit()
        self._pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass.setPlaceholderText("Optional password")
        form.addRow("Password:", self._pass)

        root.addWidget(box)

        # ── Proxy list file ───────────────────────────────────────────────────
        file_box = QGroupBox("Proxy List File (one proxy per line)")
        file_lay = QVBoxLayout(file_box)

        hint = QLabel(
            "Formats: <tt>host:port</tt>  |  <tt>host:port:user:pass</tt>  "
            "|  <tt>socks5://user:pass@host:port</tt>"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 11px; color: #888;")
        file_lay.addWidget(hint)

        row_lay = QHBoxLayout()
        self._file_label = QLabel("No file loaded")
        self._file_label.setStyleSheet("font-style: italic;")
        row_lay.addWidget(self._file_label, 1)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_proxy_file)
        row_lay.addWidget(browse_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("secondary", "true")
        clear_btn.clicked.connect(self._clear_proxy_file)
        row_lay.addWidget(clear_btn)

        file_lay.addLayout(row_lay)

        self._count_label = QLabel("")
        file_lay.addWidget(self._count_label)

        root.addWidget(file_box)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _load(self) -> None:
        s = load_settings()
        p = s.get("proxy", {})
        self._enabled.setChecked(bool(p.get("enabled")))
        self._host.setText(p.get("host", ""))
        self._port.setValue(int(p.get("port", 1080)))
        self._user.setText(p.get("username", ""))
        self._pass.setText(p.get("password", ""))

        proxy_file = s.get("proxy_file", "")
        self._update_file_label(proxy_file, s.get("proxy_list", []))

    def _browse_proxy_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Proxy List", "",
            "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return
        proxies = parse_proxy_file(path)
        if not proxies:
            QMessageBox.warning(self, "No Proxies Found",
                                "Could not parse any proxy entries from that file.")
            return
        s = load_settings()
        s["proxy_file"] = path
        s["proxy_list"] = proxies
        save_settings(s)
        self._update_file_label(path, proxies)

    def _clear_proxy_file(self) -> None:
        s = load_settings()
        s["proxy_file"] = ""
        s["proxy_list"] = []
        save_settings(s)
        self._update_file_label("", [])

    def _update_file_label(self, path: str, proxies: list) -> None:
        if path:
            self._file_label.setText(Path(path).name)
            self._count_label.setText(f"{len(proxies)} proxies loaded")
        else:
            self._file_label.setText("No file loaded")
            self._count_label.setText("")

    def _save(self) -> None:
        s = load_settings()
        s["proxy"] = {
            "enabled": self._enabled.isChecked(),
            "host": self._host.text().strip(),
            "port": self._port.value(),
            "username": self._user.text().strip(),
            "password": self._pass.text(),
        }
        save_settings(s)
        self.accept()

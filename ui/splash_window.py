"""Splash screen shown on every startup before the main window appears."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar, QHBoxLayout, QFrame

_STYLE = """
QWidget#splash_root {
    background-color: #020913;
    border: 1px solid rgba(13, 239, 168, 0.28);
    border-radius: 14px;
}
QLabel#splash_bolt {
    font-size: 40px;
    background: transparent;
    color: #0defa8;
}
QLabel#splash_title {
    font-size: 38px;
    font-weight: 900;
    letter-spacing: 10px;
    color: #0defa8;
    background: transparent;
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
}
QLabel#splash_sub {
    font-size: 10px;
    letter-spacing: 5px;
    color: #6b8faa;
    background: transparent;
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
}
QLabel#splash_tagline {
    font-size: 11px;
    color: #a8bdd4;
    letter-spacing: 1.5px;
    background: transparent;
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
}
QLabel#splash_version {
    font-size: 9px;
    color: rgba(107, 143, 170, 0.45);
    letter-spacing: 2px;
    background: transparent;
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
}
QProgressBar#splash_bar {
    background-color: rgba(13, 239, 168, 0.08);
    border: none;
    border-radius: 2px;
}
QProgressBar#splash_bar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0ab87e, stop:0.5 #0defa8, stop:1 #0ab87e);
    border-radius: 2px;
}
"""


class SplashScreen(QWidget):
    finished = pyqtSignal()

    def __init__(self, duration_ms: int = 3000) -> None:
        super().__init__()
        self.setObjectName("splash_root")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(420, 286)
        self.setStyleSheet(_STYLE)

        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )
        self._build_ui()
        self._animate(duration_ms)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 34, 0, 24)
        root.setSpacing(0)

        bolt = QLabel("⚡")
        bolt.setObjectName("splash_bolt")
        bolt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(bolt)

        root.addSpacing(4)

        title = QLabel("EMS")
        title.setObjectName("splash_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        sub = QLabel("MAIL FETCHER")
        sub.setObjectName("splash_sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(sub)

        root.addSpacing(18)

        tagline = QLabel("Precision Inbox Intelligence")
        tagline.setObjectName("splash_tagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(tagline)

        root.addSpacing(26)

        bar_wrap = QWidget()
        bar_wrap.setStyleSheet("background: transparent;")
        bar_lay = QHBoxLayout(bar_wrap)
        bar_lay.setContentsMargins(44, 0, 44, 0)
        self._bar = QProgressBar()
        self._bar.setObjectName("splash_bar")
        self._bar.setRange(0, 1000)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(3)
        bar_lay.addWidget(self._bar)
        root.addWidget(bar_wrap)

        root.addSpacing(18)

        from config.settings import APP_VERSION
        version = QLabel(f"v{APP_VERSION}  ·  PROFESSIONAL VERSION")
        version.setObjectName("splash_version")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(version)

    def _animate(self, duration_ms: int) -> None:
        self._anim = QPropertyAnimation(self._bar, b"value", self)
        self._anim.setDuration(duration_ms)
        self._anim.setStartValue(0)
        self._anim.setEndValue(1000)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.finished.connect(self.finished)
        self._anim.start()

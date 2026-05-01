"""Entry point for the EMS Mail Fetcher desktop application."""

import sys
import logging
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from config.settings import APP_NAME, LOG_FILE, LOG_LEVEL, RESOURCE_DIR
from db.database import init_db
from core.license_manager import check_license, get_license_info

_win = None
_splash = None


def setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> None:
    setup_logging()
    log = logging.getLogger(__name__)
    log.info("Starting %s", APP_NAME)

    try:
        init_db()
    except Exception:
        log.exception("Database initialisation failed")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    global _splash
    try:
        from ui.splash_window import SplashScreen
        _splash = SplashScreen(duration_ms=3000)
        _splash.show()
        _splash.finished.connect(lambda: _after_splash(app))
    except Exception:
        log.exception("Splash failed, launching directly")
        _after_splash(app)

    sys.exit(app.exec())


def _after_splash(app: QApplication) -> None:
    global _win, _splash
    log = logging.getLogger(__name__)

    if _splash is not None:
        _splash.close()
        _splash = None

    try:
        if not check_license():
            from ui.activate_window import ActivateWindow
            _win = ActivateWindow()
            _win.show()
        else:
            info = get_license_info()
            _win = _launch_main(app, info)
    except Exception:
        log.exception("Startup failed — see log for details")
        app.quit()


def _launch_main(app: QApplication, info: dict) -> "MainWindow":
    log = logging.getLogger(__name__)
    log.info("Launching main window (licensed to: %s)", info.get("name", "User"))

    base = RESOURCE_DIR / "ui"
    qss_file = base / "styles.qss"
    if qss_file.exists():
        check_path = str(base / "check_white.svg").replace("\\", "/")
        css = qss_file.read_text(encoding="utf-8").replace(
            "CHECKMARK_PATH", f'"{check_path}"'
        )
        app.setStyleSheet(css)

    from ui.main_window import MainWindow
    window = MainWindow(
        licensed_to=info.get("name", "User"),
        days_left=info.get("days_left", 0),
    )
    window.show()
    return window


if __name__ == "__main__":
    main()

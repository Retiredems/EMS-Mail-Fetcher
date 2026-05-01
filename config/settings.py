"""Application-wide constants and paths."""

import sys
from pathlib import Path

APP_NAME = "EMS Mail Fetcher"
APP_VERSION = "1.0.0"


def _user_data_dir() -> Path:
    """Writable directory for user data — safe for both dev and bundled modes."""
    if getattr(sys, "_MEIPASS", None):
        # Running as a PyInstaller bundle
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "EMS Mail Fetcher"
        elif sys.platform == "win32":
            import os
            return Path(os.environ.get("APPDATA", Path.home())) / "EMS Mail Fetcher"
        else:
            return Path.home() / ".ems_mail_fetcher"
    # Running from source
    return Path(__file__).resolve().parent.parent


def _resource_dir() -> Path:
    """Directory containing bundled read-only assets (QSS, SVG, presets)."""
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


BASE_DIR = _user_data_dir()
RESOURCE_DIR = _resource_dir()

# User-facing data directories (written at runtime)
DATA_DIR    = BASE_DIR / "data"
ARCHIVE_DIR = BASE_DIR / "archive"
EXPORT_DIR  = BASE_DIR / "exports"
LOG_DIR     = BASE_DIR / "logs"
RESULTS_DIR = BASE_DIR / "results"

DATA_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Database
DB_PATH = DATA_DIR / "email_archiver.db"
DB_URL  = f"sqlite:///{DB_PATH}"

# Logging
LOG_FILE  = LOG_DIR / "app.log"
LOG_LEVEL = "INFO"

# Encryption key file (Fernet key, generated on first run)
KEY_FILE = DATA_DIR / ".fernet.key"

# Config / presets — read from bundle assets when frozen
SERVER_PRESETS_FILE = RESOURCE_DIR / "config" / "server_presets.json"

# IMAP fetch batch size
IMAP_BATCH_SIZE = 10

# Connection timeout (seconds)
CONNECTION_TIMEOUT = 30

# Max auto-reconnect retries
MAX_RETRIES = 3

# Default worker thread count
DEFAULT_THREAD_COUNT = 5

# .eml file permissions (Unix)
EML_FILE_MODE = 0o600

"""Export archived emails as .eml files or a ZIP archive."""

import shutil
import zipfile
from pathlib import Path
from typing import Sequence

from db.models import Email


def export_emails_eml(emails: Sequence[Email], dest_dir: Path) -> int:
    """Copy .eml files for the given email records to dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for email_obj in emails:
        if email_obj.raw_eml_path:
            src = Path(email_obj.raw_eml_path)
            if src.exists():
                shutil.copy2(src, dest_dir / src.name)
                count += 1
    return count


def export_archive_zip(account_email: str, dest_path: Path) -> Path:
    """Zip the entire archive directory for one account."""
    from config.settings import ARCHIVE_DIR
    import re

    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", account_email)
    src_dir = ARCHIVE_DIR / safe
    if not src_dir.exists():
        raise FileNotFoundError(f"No archive found for {account_email}")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in src_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(src_dir.parent))

    return dest_path

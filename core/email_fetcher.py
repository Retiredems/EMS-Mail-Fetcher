"""Fetches raw emails per folder and saves them as .eml files."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from config.settings import ARCHIVE_DIR, EML_FILE_MODE
from db.database import get_session
from db.models import Email, Folder
from db import repository as repo

log = logging.getLogger(__name__)


def _safe_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)


def _eml_path(account_email: str, folder_name: str, uid: int) -> Path:
    folder_dir = ARCHIVE_DIR / _safe_name(account_email) / _safe_name(folder_name)
    folder_dir.mkdir(parents=True, exist_ok=True)
    return folder_dir / f"{uid}.eml"


def fetch_folder(
    account_id: int,
    folder_id: int,
    folder_path: str,
    client,
    *,
    save_eml: bool = True,
    skip_duplicates: bool = True,
    date_from: Optional[str] = None,
    stop_event=None,
    pause_event=None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> int:
    """
    Fetch all emails from one folder.
    Returns count of newly fetched emails.
    """
    from core.email_parser import parse_and_store_contacts

    with get_session() as session:
        account = repo.get_account_by_id(session, account_id)
        account_email = account.email
        folder = session.get(Folder, folder_id)
        last_uid = folder.last_uid if folder else None

    total = client.select_folder(folder_path)

    with get_session() as session:
        f = session.get(Folder, folder_id)
        if f:
            repo.update_folder_progress(session, f, fetched=0, total=total, status="fetching")

    uids = client.get_uid_list(
        since_uid=last_uid if skip_duplicates else None,
        date_filter=date_from,
    )
    if not uids:
        with get_session() as session:
            f = session.get(Folder, folder_id)
            if f:
                repo.update_folder_progress(session, f, fetched=f.fetched_emails, status="done")
        return 0

    fetched_count = 0
    max_uid_seen = last_uid or 0

    for uid, raw_bytes in client.fetch_raw_emails(uids):
        if stop_event and stop_event.is_set():
            break
        if pause_event:
            while pause_event.is_set():
                import time
                time.sleep(0.5)

        with get_session() as session:
            if skip_duplicates and repo.email_uid_exists(session, account_id, folder_id, uid):
                continue

            eml_path = None
            if save_eml:
                p = _eml_path(account_email, folder_path, uid)
                p.write_bytes(raw_bytes)
                try:
                    os.chmod(p, EML_FILE_MODE)
                except OSError:
                    pass
                eml_path = str(p)

            subject, from_addr, date_sent, message_id = _parse_headers(raw_bytes)

            if skip_duplicates and message_id and repo.email_message_id_exists(
                session, account_id, message_id
            ):
                continue

            email_obj = repo.create_email(
                session,
                account_id=account_id,
                folder_id=folder_id,
                uid=uid,
                message_id=message_id,
                subject=subject,
                from_address=from_addr,
                date_sent=date_sent,
                raw_size_bytes=len(raw_bytes),
                raw_eml_path=eml_path,
            )

            parse_and_store_contacts(session, account_id, email_obj.id, raw_bytes, date_sent)
            repo.mark_email_parsed(session, email_obj)

            fetched_count += 1
            if uid > max_uid_seen:
                max_uid_seen = uid

            f = session.get(Folder, folder_id)
            if f:
                repo.update_folder_progress(
                    session, f, fetched=f.fetched_emails + 1, last_uid=max_uid_seen
                )

        if progress_cb:
            progress_cb(fetched_count, total)

    with get_session() as session:
        f = session.get(Folder, folder_id)
        if f:
            repo.update_folder_progress(
                session, f, fetched=f.fetched_emails, status="done", last_uid=max_uid_seen
            )

    return fetched_count


def _parse_headers(raw_bytes: bytes) -> tuple:
    import email as email_lib
    import email.policy
    from email.utils import parsedate_to_datetime

    try:
        msg = email_lib.message_from_bytes(raw_bytes, policy=email_lib.policy.default)
        subject = str(msg.get("Subject", ""))[:500]
        from_addr = str(msg.get("From", ""))[:320]
        message_id = str(msg.get("Message-ID", "")).strip() or None
        date_sent = None
        date_str = str(msg.get("Date", ""))
        if date_str:
            try:
                date_sent = parsedate_to_datetime(date_str)
                if date_sent.tzinfo is None:
                    date_sent = date_sent.replace(tzinfo=timezone.utc)
            except Exception:
                pass
        return subject, from_addr, date_sent, message_id
    except Exception:
        return "", "", None, None

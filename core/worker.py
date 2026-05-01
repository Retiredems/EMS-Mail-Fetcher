"""Background worker thread — emits Qt signals for the main table."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from config.settings import MAX_RETRIES, RESULTS_DIR
from core.account_manager import update_account_status
from core import connector
from core.folder_crawler import crawl_and_store_folders
from db.database import get_session
from db import repository as repo

log = logging.getLogger(__name__)


class WorkerSignals(QObject):
    status_changed  = pyqtSignal(int, str)          # account_id, message
    server_detected = pyqtSignal(int, str)          # account_id, "host:port"
    finished        = pyqtSignal(int, bool, int, int, int)
    # account_id, success, contacts_found, emails_fetched, folders_done
    error           = pyqtSignal(int, str)          # account_id, error_msg


class FetchWorker(threading.Thread):
    def __init__(
        self,
        account_id: int,
        signals: WorkerSignals,
        *,
        save_eml: bool = True,
        skip_duplicates: bool = True,
        date_from: Optional[str] = None,
        proxy: Optional[dict] = None,
        save_results: bool = False,
        save_attachments: bool = False,
    ) -> None:
        super().__init__(daemon=True)
        self.account_id       = account_id
        self.signals          = signals
        self.save_eml         = save_eml
        self.skip_duplicates  = skip_duplicates
        self.date_from        = date_from
        self.proxy            = proxy
        self.save_results     = save_results
        self.save_attachments = save_attachments
        self._stop_event     = threading.Event()
        self._pause_event    = threading.Event()

    def stop(self)  -> None: self._stop_event.set()
    def pause(self) -> None: self._pause_event.set()
    def resume(self)-> None: self._pause_event.clear()

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        aid = self.account_id
        sig = self.signals
        emails_fetched = contacts_found = folders_done = 0
        password_plain = ""
        email_addr = str(aid)  # safe fallback before the DB read succeeds

        try:
            with get_session() as session:
                account = repo.get_account_by_id(session, aid)
                if account is None:
                    sig.finished.emit(aid, False, 0, 0, 0)
                    return
                from types import SimpleNamespace
                acct = SimpleNamespace(
                    id=account.id,
                    email=account.email,
                    protocol=account.protocol or "IMAP",
                    server=account.server or "",
                    port=account.port or 993,
                    use_ssl=account.use_ssl,
                    username=account.username or account.email,
                )

            email_addr  = acct.email
            server      = acct.server
            port        = acct.port

            # Get plain password for log entries
            from core.account_manager import get_account_password
            password_plain = get_account_password(aid) or ""

            if self._stop_event.is_set():
                sig.finished.emit(aid, False, 0, 0, 0)
                return

            sig.status_changed.emit(aid, "Connecting…")
            update_account_status(aid, "running")

            client = connector.get_client(acct, proxy=self.proxy, stop_event=self._stop_event)
            client.connect()

            if self._stop_event.is_set():
                client.disconnect()
                update_account_status(aid, "error")
                sig.finished.emit(aid, False, 0, 0, 0)
                return

            sig.server_detected.emit(aid, f"{server}:{port}")

            sig.status_changed.emit(aid, "Listing folders…")
            folders = crawl_and_store_folders(aid, client)
            active  = [f for f in folders if not f["is_excluded"]]
            total_folders = len(active)

            if not active:
                client.disconnect()
                self._log_success(email_addr, password_plain, 0, 0, 0)
                sig.finished.emit(aid, True, 0, 0, 0)
                return

            result_emails: set[str] = set()

            for f in active:
                if self._stop_event.is_set():
                    break
                while self._pause_event.is_set():
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.5)

                folder_path = f["full_path"]
                folder_name = f["name"]
                folder_id   = f["id"]

                sig.status_changed.emit(
                    aid,
                    f"Fetching {folder_name} ({folders_done + 1}/{total_folders})"
                )

                try:
                    fetched, _ = self._fetch_folder(
                        aid, email_addr, folder_id, folder_path, client, result_emails
                    )
                    emails_fetched += fetched
                    contacts_found  = len(result_emails)
                except Exception as exc:
                    log.error("Folder %s error: %s", folder_path, exc, exc_info=True)
                    sig.error.emit(aid, f"{folder_name}: {exc}")

                folders_done += 1
                sig.status_changed.emit(
                    aid,
                    f"Fetching {folder_name} ({folders_done}/{total_folders}) "
                    f"— {emails_fetched:,} mails, {contacts_found:,} contacts"
                )

            client.disconnect()

            if result_emails:
                self._save_contacts(email_addr, result_emails)

            if self.save_results:
                self._log_success(email_addr, password_plain, contacts_found, emails_fetched, folders_done)
            update_account_status(aid, "done")
            with get_session() as session:
                a = repo.get_account_by_id(session, aid)
                if a:
                    repo.update_account(session, a, last_synced_at=datetime.now(timezone.utc))

            sig.finished.emit(aid, True, contacts_found, emails_fetched, folders_done)

        except Exception as exc:
            log.exception("Worker fatal error account %d: %s", aid, exc)
            update_account_status(aid, "error")
            if self.save_results:
                self._log_failure(email_addr, password_plain, str(exc))
            sig.error.emit(aid, str(exc))
            sig.finished.emit(aid, False, contacts_found, emails_fetched, folders_done)

    # ── Folder fetch ──────────────────────────────────────────────────────────

    def _fetch_folder(
        self,
        account_id: int,
        account_email: str,
        folder_id: int,
        folder_path: str,
        client,
        result_emails: set,
    ) -> tuple[int, int]:
        from core.email_fetcher import _parse_headers, _eml_path
        from core.email_parser import extract_addresses
        from config.settings import EML_FILE_MODE
        import email as email_lib
        import email.policy
        import os

        client.select_folder(folder_path)
        uids = client.get_uid_list(date_filter=self.date_from)
        if not uids:
            return 0, 0

        fetched = 0
        for uid, raw_bytes in client.fetch_raw_emails(uids):
            if self._stop_event.is_set():
                break

            try:
                msg = email_lib.message_from_bytes(raw_bytes, policy=email_lib.policy.default)
                for _name, addr in extract_addresses(msg):
                    result_emails.add(addr.lower())
                if self.save_attachments:
                    self._extract_attachments(msg, account_email, uid)
                del msg
            except Exception:
                pass

            subject, from_addr, date_sent, message_id = _parse_headers(raw_bytes)

            with get_session() as session:
                if self.skip_duplicates and repo.email_uid_exists(session, account_id, folder_id, uid):
                    del raw_bytes
                    continue
                if self.skip_duplicates and message_id and repo.email_message_id_exists(
                    session, account_id, message_id
                ):
                    del raw_bytes
                    continue

                eml_path = None
                if self.save_eml:
                    p = _eml_path(account_email, folder_path, uid)
                    p.write_bytes(raw_bytes)
                    try:
                        os.chmod(p, EML_FILE_MODE)
                    except OSError:
                        pass
                    eml_path = str(p)

                repo.create_email(
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
                fetched += 1

            del raw_bytes  # release email bytes immediately after each message

        return fetched, len(result_emails)

    # ── Results & logs ────────────────────────────────────────────────────────

    def _extract_attachments(self, msg, account_email: str, uid: int) -> None:
        attach_dir = RESULTS_DIR / "attachments" / account_email
        attach_dir.mkdir(parents=True, exist_ok=True)
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            disposition = part.get("Content-Disposition", "")
            filename = part.get_filename()
            if not filename and "attachment" not in disposition.lower():
                continue
            if not filename:
                filename = f"attachment.{part.get_content_subtype() or 'bin'}"
            safe = "".join(c for c in filename if c not in r'\/:*?"<>|' and ord(c) >= 32).strip() or "attachment"
            payload = part.get_payload(decode=True)
            if payload:
                try:
                    (attach_dir / f"{uid}_{safe}").write_bytes(payload)
                except Exception as exc:
                    log.warning("Could not save attachment %s uid %d: %s", safe, uid, exc)
                finally:
                    del payload

    def _save_contacts(self, account_email: str, emails: set[str]) -> None:
        """Save extracted contacts to results/<email@domain.com>.txt"""
        path = RESULTS_DIR / f"{account_email}.txt"
        existing: set[str] = set()
        if path.exists():
            existing = {ln.strip().lower() for ln in path.read_text().splitlines() if ln.strip()}
        merged = sorted(existing | emails)
        path.write_text("\n".join(merged) + "\n", encoding="utf-8")
        log.info("Saved %d contacts → %s", len(merged), path)

    def _log_success(
        self, email: str, password: str, contacts: int, mails: int, folders: int
    ) -> None:
        _append_log("success.txt", f"{email}:{password}\n")

    def _log_failure(self, email: str, password: str, error: str) -> None:
        _append_log("failed.txt", f"{email}:{password}\n")


def _append_log(filename: str, line: str) -> None:
    path = RESULTS_DIR / filename
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception as exc:
        log.warning("Could not write %s: %s", filename, exc)


class WorkerManager:
    def __init__(self) -> None:
        self._workers: dict[int, FetchWorker] = {}
        self.signals = WorkerSignals()

    def start_account(self, account_id: int, **kwargs) -> None:
        if account_id in self._workers and self._workers[account_id].is_alive():
            return
        w = FetchWorker(account_id, self.signals, **kwargs)
        self._workers[account_id] = w
        w.start()

    def stop_account(self, account_id: int)  -> None:
        if w := self._workers.get(account_id): w.stop()

    def pause_account(self, account_id: int) -> None:
        if w := self._workers.get(account_id): w.pause()

    def resume_account(self, account_id: int)-> None:
        if w := self._workers.get(account_id): w.resume()

    def stop_all(self)  -> None:
        for w in self._workers.values(): w.stop()

    def pause_all(self) -> None:
        for w in self._workers.values(): w.pause()

    def resume_all(self)-> None:
        for w in self._workers.values(): w.resume()

    def running_count(self) -> int:
        return sum(1 for w in self._workers.values() if w.is_alive())

    def is_running(self, account_id: int) -> bool:
        w = self._workers.get(account_id)
        return w is not None and w.is_alive()

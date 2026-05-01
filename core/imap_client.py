"""IMAP protocol client with UID-based fetching, auto-reconnect, and SOCKS5 proxy."""

from __future__ import annotations

import imaplib
import logging
import ssl
import time
from typing import Iterator, Optional

from config.settings import CONNECTION_TIMEOUT, IMAP_BATCH_SIZE, MAX_RETRIES
from core.account_manager import get_account_password

log = logging.getLogger(__name__)


def _get_proxy_cfg() -> Optional[dict]:
    """Return active proxy config dict or None."""
    try:
        from ui.settings_dialog import load_settings
        s = load_settings()
        p = s.get("proxy", {})
        if p.get("enabled") and p.get("host"):
            return p
    except Exception:
        pass
    return None


def _make_imap_ssl(host: str, port: int, ssl_ctx: ssl.SSLContext, proxy: Optional[dict]) -> imaplib.IMAP4:
    """Create an IMAP4_SSL connection, optionally tunnelled through SOCKS5."""
    if proxy:
        try:
            import socks

            class _ProxiedIMAP4SSL(imaplib.IMAP4):
                def _create_socket(self, timeout):
                    raw = socks.socksocket()
                    raw.set_proxy(
                        socks.SOCKS5,
                        proxy["host"],
                        int(proxy["port"]),
                        username=proxy.get("username") or None,
                        password=proxy.get("password") or None,
                    )
                    raw.settimeout(timeout or CONNECTION_TIMEOUT)
                    raw.connect((self.host, self.port))
                    return ssl_ctx.wrap_socket(raw, server_hostname=self.host)

            return _ProxiedIMAP4SSL(host, port)
        except ImportError:
            log.warning("PySocks not installed — connecting without proxy")

    return imaplib.IMAP4_SSL(host, port, ssl_context=ssl_ctx, timeout=CONNECTION_TIMEOUT)


def _make_imap_plain(host: str, port: int, proxy: Optional[dict]) -> imaplib.IMAP4:
    """Create a plain IMAP4 connection, optionally tunnelled through SOCKS5."""
    if proxy:
        try:
            import socks

            class _ProxiedIMAP4(imaplib.IMAP4):
                def _create_socket(self, timeout):
                    raw = socks.socksocket()
                    raw.set_proxy(
                        socks.SOCKS5,
                        proxy["host"],
                        int(proxy["port"]),
                        username=proxy.get("username") or None,
                        password=proxy.get("password") or None,
                    )
                    raw.settimeout(timeout or CONNECTION_TIMEOUT)
                    raw.connect((self.host, self.port))
                    return raw

            return _ProxiedIMAP4(host, port)
        except ImportError:
            pass

    return imaplib.IMAP4(host, port, timeout=CONNECTION_TIMEOUT)


class IMAPClient:
    def __init__(self, account, proxy: Optional[dict] = None, stop_event=None) -> None:
        self.account = account
        self._proxy = proxy
        self._stop_event = stop_event
        self._imap: Optional[imaplib.IMAP4] = None

    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep in 0.2s chunks so the stop_event can break the wait early."""
        end = time.time() + seconds
        while time.time() < end:
            if self._stop_event and self._stop_event.is_set():
                return
            time.sleep(0.2)

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        server   = self.account.server
        port     = self.account.port or 993
        use_ssl  = getattr(self.account, "use_ssl", True)
        username = self.account.username or self.account.email
        password = get_account_password(self.account.id)
        proxy    = self._proxy if self._proxy is not None else _get_proxy_cfg()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if use_ssl:
                    ctx = ssl.create_default_context()
                    self._imap = _make_imap_ssl(server, port, ctx, proxy)
                else:
                    self._imap = _make_imap_plain(server, port, proxy)
                    try:
                        self._imap.starttls()
                    except Exception:
                        pass

                self._imap.socket().settimeout(CONNECTION_TIMEOUT)
                self._imap.login(username, password)
                log.info("IMAP connected: %s@%s", username, server)
                return
            except imaplib.IMAP4.error as exc:
                log.error("IMAP auth error (%s): %s", self.account.email, exc)
                raise
            except ssl.SSLCertVerificationError:
                # Certificate mismatch / self-signed — retry without verification
                log.warning("SSL cert verify failed for %s — retrying without verification", server)
                try:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    self._imap = _make_imap_ssl(server, port, ctx, proxy)
                    self._imap.socket().settimeout(CONNECTION_TIMEOUT)
                    self._imap.login(username, password)
                    log.info("IMAP connected (unverified SSL): %s@%s", username, server)
                    return
                except imaplib.IMAP4.error as exc:
                    log.error("IMAP auth error (%s): %s", self.account.email, exc)
                    raise
                except Exception as exc:
                    log.warning("IMAP unverified attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
                    if attempt == MAX_RETRIES:
                        raise
                    self._interruptible_sleep(2 ** attempt)
            except Exception as exc:
                log.warning("IMAP connect attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
                if attempt == MAX_RETRIES:
                    raise
                self._interruptible_sleep(2 ** attempt)

    def disconnect(self) -> None:
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None

    def _ensure_connected(self) -> None:
        if self._imap is None:
            self.connect()

    # ── Folder listing ────────────────────────────────────────────────────────

    def list_folders(self) -> list[dict]:
        self._ensure_connected()
        result = []
        _status, raw_list = self._imap.list()  # type: ignore[union-attr]
        for item in raw_list or []:
            if item is None:
                continue
            decoded = item.decode("utf-8", errors="replace") if isinstance(item, bytes) else item
            # Parse: (\Flags) "delimiter" "folder name"
            try:
                flags_end = decoded.index(")") + 1
                rest = decoded[flags_end:].strip()
                # delimiter is either "." or "/" in quotes or NIL
                if rest.startswith('"'):
                    delim_end = rest.index('"', 1) + 1
                    rest = rest[delim_end:].strip()
                else:
                    rest = rest.split(" ", 1)[-1].strip() if " " in rest else rest
                folder_name = rest.strip().strip('"')
            except Exception:
                parts = decoded.rsplit(" ", 1)
                folder_name = parts[-1].strip().strip('"')

            flags_part = decoded.split("(")[1].split(")")[0] if "(" in decoded else ""
            flags = [f.strip().lstrip("\\") for f in flags_part.split()]

            result.append({
                "name": folder_name.split("/")[-1].split(".")[-1] if ("/" in folder_name or "." in folder_name) else folder_name,
                "full_path": folder_name,
                "flags": flags,
            })
        return result

    # ── Email fetching ────────────────────────────────────────────────────────

    def select_folder(self, full_path: str) -> int:
        self._ensure_connected()
        try:
            _status, data = self._imap.select(f'"{full_path}"')  # type: ignore[union-attr]
        except Exception:
            _status, data = self._imap.select(full_path)  # type: ignore[union-attr]
        return int(data[0]) if data and data[0] else 0

    def get_uid_list(self, since_uid: Optional[int] = None, date_filter: Optional[str] = None) -> list[int]:
        self._ensure_connected()
        criteria = "ALL"
        if since_uid:
            criteria = f"UID {since_uid + 1}:*"
        elif date_filter:
            criteria = f"SINCE {date_filter}"
        _status, data = self._imap.uid("search", None, criteria)  # type: ignore[union-attr]
        if not data or not data[0]:
            return []
        return [int(u) for u in data[0].split()]

    def fetch_raw_emails(self, uids: list[int]) -> Iterator[tuple[int, bytes]]:
        self._ensure_connected()
        for i in range(0, len(uids), IMAP_BATCH_SIZE):
            batch = uids[i: i + IMAP_BATCH_SIZE]
            uid_set = ",".join(str(u) for u in batch)
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    _status, data = self._imap.uid("fetch", uid_set, "(RFC822)")  # type: ignore[union-attr]
                    break
                except Exception as exc:
                    log.warning("Fetch attempt %d failed: %s", attempt, exc)
                    if attempt == MAX_RETRIES:
                        raise
                    self._interruptible_sleep(2 ** attempt)
                    self.connect()

            uid_idx = 0
            for item in data or []:
                if isinstance(item, tuple) and len(item) == 2:
                    raw_bytes = item[1]
                    uid = batch[uid_idx] if uid_idx < len(batch) else batch[-1]
                    try:
                        header = item[0].decode("utf-8", errors="replace") if isinstance(item[0], bytes) else str(item[0])
                        for tok in header.split():
                            if tok.isdigit():
                                uid = int(tok)
                                break
                    except Exception:
                        pass
                    yield uid, raw_bytes
                    uid_idx += 1

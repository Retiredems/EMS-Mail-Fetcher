"""POP3 protocol client with optional SOCKS5 proxy."""

from __future__ import annotations

import logging
import poplib
import ssl
import time
from typing import Iterator, Optional

from config.settings import CONNECTION_TIMEOUT, MAX_RETRIES
from core.account_manager import get_account_password

log = logging.getLogger(__name__)


def _get_proxy_cfg() -> Optional[dict]:
    try:
        from ui.settings_dialog import load_settings
        s = load_settings()
        p = s.get("proxy", {})
        if p.get("enabled") and p.get("host"):
            return p
    except Exception:
        pass
    return None


def _make_pop3_ssl(host: str, port: int, proxy: Optional[dict]) -> poplib.POP3:
    if proxy:
        try:
            import socks, socket
            raw = socks.socksocket()
            raw.set_proxy(
                socks.SOCKS5, proxy["host"], int(proxy["port"]),
                username=proxy.get("username") or None,
                password=proxy.get("password") or None,
            )
            raw.settimeout(CONNECTION_TIMEOUT)
            raw.connect((host, port))
            ctx = ssl.create_default_context()
            ssl_sock = ctx.wrap_socket(raw, server_hostname=host)
            pop = poplib.POP3.__new__(poplib.POP3)
            pop.sock = ssl_sock
            pop.file = ssl_sock.makefile("rb")
            pop.host = host
            pop.port = port
            pop.DEBUGLEVEL = 0
            pop._resp = pop._getresp()
            return pop
        except ImportError:
            pass
    ctx = ssl.create_default_context()
    return poplib.POP3_SSL(host, port, context=ctx)


class POP3Client:
    def __init__(self, account, proxy: Optional[dict] = None, stop_event=None) -> None:
        self.account = account
        self._proxy = proxy
        self._stop_event = stop_event
        self._pop: Optional[poplib.POP3] = None

    def _interruptible_sleep(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            if self._stop_event and self._stop_event.is_set():
                return
            time.sleep(0.2)

    def connect(self) -> None:
        server = self.account.server
        port = self.account.port or 995
        use_ssl = getattr(self.account, "use_ssl", True)
        username = self.account.username or self.account.email
        password = get_account_password(self.account.id)
        proxy = self._proxy if self._proxy is not None else _get_proxy_cfg()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if use_ssl:
                    self._pop = _make_pop3_ssl(server, port, proxy)
                else:
                    self._pop = poplib.POP3(server, port)
                self._pop.sock.settimeout(CONNECTION_TIMEOUT)
                self._pop.user(username)
                self._pop.pass_(password)
                log.info("POP3 connected: %s@%s", username, server)
                return
            except poplib.error_proto as exc:
                log.error("POP3 auth error: %s", exc)
                raise
            except ssl.SSLCertVerificationError:
                log.warning("POP3 SSL cert verify failed for %s — retrying without verification", server)
                try:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    self._pop = poplib.POP3_SSL(server, port, context=ctx)
                    self._pop.sock.settimeout(CONNECTION_TIMEOUT)
                    self._pop.user(username)
                    self._pop.pass_(password)
                    log.info("POP3 connected (unverified SSL): %s@%s", username, server)
                    return
                except poplib.error_proto as exc:
                    raise
                except Exception as exc:
                    if attempt == MAX_RETRIES:
                        raise
                    self._interruptible_sleep(2 ** attempt)
            except Exception as exc:
                log.warning("POP3 connect attempt %d/%d: %s", attempt, MAX_RETRIES, exc)
                if attempt == MAX_RETRIES:
                    raise
                self._interruptible_sleep(2 ** attempt)

    def disconnect(self) -> None:
        if self._pop:
            try:
                self._pop.quit()
            except Exception:
                pass
            self._pop = None

    def list_folders(self) -> list[dict]:
        return [{"name": "INBOX", "full_path": "INBOX", "flags": []}]

    def select_folder(self, full_path: str) -> int:
        """POP3 has no real folder selection; always operates on INBOX."""
        return self.get_message_count()

    def get_uid_list(
        self,
        since_uid: "Optional[int]" = None,
        date_filter: "Optional[str]" = None,
    ) -> list[int]:
        """Return 1-based message numbers as the UID list for POP3."""
        count = self.get_message_count()
        uids = list(range(1, count + 1))
        if since_uid:
            uids = [u for u in uids if u > since_uid]
        return uids

    def get_message_count(self) -> int:
        if self._pop is None:
            self.connect()
        count, _ = self._pop.stat()  # type: ignore[union-attr]
        return count

    def fetch_raw_emails(
        self, uids: "Optional[list[int]]" = None
    ) -> Iterator[tuple[int, bytes]]:
        """Fetch raw email bytes.

        *uids* is a list of 1-based message numbers (as returned by
        get_uid_list).  When omitted or None the entire mailbox is fetched,
        mirroring the original behaviour.
        """
        if self._pop is None:
            self.connect()
        if uids is None:
            count = self.get_message_count()
            uids = list(range(1, count + 1))
        for num in uids:
            try:
                _resp, lines, _octets = self._pop.retr(num)  # type: ignore[union-attr]
                yield num, b"\r\n".join(lines)
            except Exception as exc:
                log.warning("POP3 fetch msg %d failed: %s", num, exc)

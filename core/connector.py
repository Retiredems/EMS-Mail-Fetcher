"""Protocol router — returns the right client for an account."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from db.models import Account

log = logging.getLogger(__name__)


def get_client(account: "Account", proxy: "Optional[dict]" = None, stop_event=None):
    """Return an initialised (but not yet connected) protocol client."""
    protocol = (account.protocol or "").upper()

    if protocol == "IMAP":
        from core.imap_client import IMAPClient
        return IMAPClient(account, proxy=proxy, stop_event=stop_event)

    if protocol == "POP3":
        from core.pop3_client import POP3Client
        return POP3Client(account, proxy=proxy, stop_event=stop_event)

    if protocol == "EXCHANGE":
        from core.exchange_client import ExchangeClient
        return ExchangeClient(account)

    if protocol == "GMAIL_OAUTH":
        from core.gmail_oauth import GmailOAuthClient
        return GmailOAuthClient(account)

    if protocol == "OUTLOOK_OAUTH":
        from core.outlook_oauth import OutlookOAuthClient
        return OutlookOAuthClient(account)

    raise ValueError(f"Unknown protocol: {account.protocol!r}")


def test_connection(account_data: dict) -> tuple[bool, str]:
    """
    Test a connection using a plain dict (before the account is saved).
    Returns (success, message).
    """
    from types import SimpleNamespace

    # Build a throwaway account-like object
    acct = SimpleNamespace(**account_data)
    try:
        client = get_client(acct)  # type: ignore[arg-type]
        client.connect()
        client.disconnect()
        return True, "Connection successful"
    except Exception as exc:
        log.warning("Connection test failed: %s", exc)
        return False, str(exc)

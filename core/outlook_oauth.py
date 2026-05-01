"""Microsoft OAuth2 (MSAL) for Outlook / Office 365 via IMAP XOAUTH2."""

from __future__ import annotations

import base64
import imaplib
import logging
import ssl
from typing import Optional

log = logging.getLogger(__name__)

# Public multi-tenant app client ID (works for personal Outlook/Hotmail).
# For Office 365 tenants, replace with your registered app's client ID.
MICROSOFT_CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["https://outlook.office365.com/IMAP.AccessAsUser.All", "offline_access"]


def run_oauth_flow(account_id: int) -> dict:
    """
    Device-code flow — prints a URL + code the user visits in a browser.
    Returns token dict and persists it.
    """
    import msal
    from core.account_manager import save_account_oauth_token

    app = msal.PublicClientApplication(MICROSOFT_CLIENT_ID, authority=AUTHORITY)
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"MSAL device flow failed: {flow}")

    print(flow["message"])  # shown in UI via caller
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        raise RuntimeError(f"MSAL token acquisition failed: {result.get('error_description')}")

    save_account_oauth_token(account_id, result)
    log.info("Outlook OAuth token saved for account_id=%d", account_id)
    return result


def get_valid_token(account_id: int) -> Optional[str]:
    """Return a valid access token, refreshing with MSAL if needed."""
    import msal
    from core.account_manager import get_account_oauth_token, save_account_oauth_token

    token_data = get_account_oauth_token(account_id)
    if not token_data:
        return None

    app = msal.PublicClientApplication(MICROSOFT_CLIENT_ID, authority=AUTHORITY)
    accounts = app.get_accounts()

    # Try silent refresh
    result = None
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if not result and "refresh_token" in token_data:
        result = app.acquire_token_by_refresh_token(token_data["refresh_token"], scopes=SCOPES)

    if result and "access_token" in result:
        save_account_oauth_token(account_id, result)
        return result["access_token"]

    return token_data.get("access_token")


def _build_xoauth2_string(user: str, access_token: str) -> str:
    auth_string = f"user={user}\x01auth=Bearer {access_token}\x01\x01"
    return base64.b64encode(auth_string.encode()).decode()


class OutlookOAuthClient:
    """IMAP client for Outlook using XOAUTH2."""

    def __init__(self, account) -> None:
        self.account = account
        self._imap: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> None:
        access_token = get_valid_token(self.account.id)
        if not access_token:
            raise RuntimeError(
                f"No valid OAuth token for {self.account.email}. "
                "Please re-authorise the account."
            )

        ctx = ssl.create_default_context()
        self._imap = imaplib.IMAP4_SSL("outlook.office365.com", 993, ssl_context=ctx)
        auth_string = _build_xoauth2_string(self.account.email, access_token)
        self._imap.authenticate("XOAUTH2", lambda _: auth_string)
        log.info("Outlook IMAP connected via OAuth: %s", self.account.email)

    def disconnect(self) -> None:
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None

    def list_folders(self) -> list[dict]:
        from core.imap_client import IMAPClient
        proxy = IMAPClient.__new__(IMAPClient)
        proxy.account = self.account
        proxy._imap = self._imap
        return proxy.list_folders()

    def select_folder(self, full_path: str) -> int:
        from core.imap_client import IMAPClient
        proxy = IMAPClient.__new__(IMAPClient)
        proxy.account = self.account
        proxy._imap = self._imap
        return proxy.select_folder(full_path)

    def get_uid_list(self, since_uid=None, date_filter=None) -> list[int]:
        from core.imap_client import IMAPClient
        proxy = IMAPClient.__new__(IMAPClient)
        proxy.account = self.account
        proxy._imap = self._imap
        return proxy.get_uid_list(since_uid=since_uid, date_filter=date_filter)

    def fetch_raw_emails(self, uids: list[int]):
        from core.imap_client import IMAPClient
        proxy = IMAPClient.__new__(IMAPClient)
        proxy.account = self.account
        proxy._imap = self._imap
        yield from proxy.fetch_raw_emails(uids)

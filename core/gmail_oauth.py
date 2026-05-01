"""Gmail OAuth2 flow using google-auth + IMAP XOAUTH2."""

from __future__ import annotations

import base64
import imaplib
import json
import logging
import ssl
import webbrowser
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

SCOPES = [
    "https://mail.google.com/",
]

# Instructions for the user: create OAuth credentials at console.cloud.google.com
# and place the downloaded client_secret.json in the config/ directory.
CLIENT_SECRET_FILE = Path(__file__).resolve().parent.parent / "config" / "gmail_client_secret.json"


def get_oauth_credentials(account_id: int):
    """Return valid google.oauth2.credentials.Credentials, refreshing if needed."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from core.account_manager import get_account_oauth_token, save_account_oauth_token

    token_data = get_account_oauth_token(account_id)
    if token_data:
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_account_oauth_token(account_id, json.loads(creds.to_json()))
        if creds.valid:
            return creds

    return None


def run_oauth_flow(account_id: int) -> dict:
    """
    Run the browser-based OAuth2 flow and return token dict.
    Requires gmail_client_secret.json in config/.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow
    from core.account_manager import save_account_oauth_token

    if not CLIENT_SECRET_FILE.exists():
        raise FileNotFoundError(
            f"Gmail OAuth credentials not found at {CLIENT_SECRET_FILE}.\n"
            "Download your OAuth 2.0 Client ID from Google Cloud Console and save it there."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    token_dict = json.loads(creds.to_json())
    save_account_oauth_token(account_id, token_dict)
    log.info("Gmail OAuth token saved for account_id=%d", account_id)
    return token_dict


def _build_xoauth2_string(user: str, access_token: str) -> str:
    auth_string = f"user={user}\x01auth=Bearer {access_token}\x01\x01"
    return base64.b64encode(auth_string.encode()).decode()


class GmailOAuthClient:
    """IMAP client that authenticates via OAuth2 XOAUTH2."""

    def __init__(self, account) -> None:
        self.account = account
        self._imap: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> None:
        from core.imap_client import IMAPClient as _Base

        creds = get_oauth_credentials(self.account.id)
        if creds is None:
            raise RuntimeError(
                f"No valid OAuth token for {self.account.email}. "
                "Please re-authorise the account."
            )

        ctx = ssl.create_default_context()
        self._imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ctx)
        auth_string = _build_xoauth2_string(self.account.email, creds.token)
        self._imap.authenticate("XOAUTH2", lambda _: auth_string)
        log.info("Gmail IMAP connected via OAuth: %s", self.account.email)

    def disconnect(self) -> None:
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None

    # Delegate folder listing and email fetching to the shared IMAP helpers
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

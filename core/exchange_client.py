"""Microsoft Exchange / EWS client via exchangelib."""

from __future__ import annotations

import logging
from typing import Iterator, Optional

from core.account_manager import get_account_password

log = logging.getLogger(__name__)


class ExchangeClient:
    def __init__(self, account) -> None:
        self.account = account
        self._account_obj = None  # exchangelib Account object

    def connect(self) -> None:
        try:
            from exchangelib import (
                Account as EWSAccount,
                Credentials,
                Configuration,
                DELEGATE,
            )
        except ImportError:
            raise RuntimeError("exchangelib is not installed — run: pip install exchangelib")

        password = get_account_password(self.account.id)
        creds = Credentials(
            username=self.account.username or self.account.email,
            password=password,
        )

        if self.account.server:
            config = Configuration(server=self.account.server, credentials=creds)
            self._account_obj = EWSAccount(
                primary_smtp_address=self.account.email,
                config=config,
                autodiscover=False,
                access_type=DELEGATE,
            )
        else:
            self._account_obj = EWSAccount(
                primary_smtp_address=self.account.email,
                credentials=creds,
                autodiscover=True,
                access_type=DELEGATE,
            )
        log.info("Exchange connected: %s", self.account.email)

    def disconnect(self) -> None:
        self._account_obj = None

    def list_folders(self) -> list[dict]:
        if self._account_obj is None:
            self.connect()
        folders = []
        for folder in self._account_obj.root.walk():  # type: ignore[union-attr]
            try:
                folders.append({
                    "name": folder.name,
                    "full_path": str(folder.absolute),
                    "flags": [],
                })
            except Exception:
                pass
        return folders

    def fetch_raw_emails(self, folder_path: str) -> Iterator[tuple[str, bytes]]:
        """Yield (item_id, raw_mime_bytes) for each email in the folder."""
        if self._account_obj is None:
            self.connect()
        try:
            folder = self._account_obj.root  # type: ignore[union-attr]
            for part in folder_path.split("/"):
                folder = folder / part
            for item in folder.all():
                try:
                    mime_bytes = item.mime_content
                    if mime_bytes:
                        yield str(item.id), mime_bytes
                except Exception as exc:
                    log.warning("Exchange fetch item failed: %s", exc)
        except Exception as exc:
            log.error("Exchange folder %s error: %s", folder_path, exc)

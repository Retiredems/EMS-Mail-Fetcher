"""Parse email headers and extract/store contacts."""

from __future__ import annotations

import email
import email.policy
import logging
import re
from datetime import datetime, timezone
from email.utils import getaddresses
from typing import Optional

from db import repository as repo
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

# Header fields that may contain email addresses
CONTACT_HEADERS = ("From", "To", "CC", "BCC", "Reply-To", "Sender")

# Fallback regex for malformed headers
_EMAIL_RE = re.compile(r"[\w.%+\-]+@[\w.\-]+\.[a-zA-Z]{2,}")


def extract_addresses(msg) -> list[tuple[str, str]]:
    """
    Return list of (display_name, email_address) from all contact headers.
    email_address is guaranteed non-empty; display_name may be empty.
    """
    raw_pairs: list[tuple[str, str]] = []

    for header in CONTACT_HEADERS:
        values = msg.get_all(header, [])
        for val in values:
            try:
                parsed = getaddresses([str(val)])
                for name, addr in parsed:
                    addr = addr.strip().lower()
                    if addr and "@" in addr:
                        raw_pairs.append((name.strip(), addr))
            except Exception:
                # Fallback regex
                for addr in _EMAIL_RE.findall(str(val)):
                    raw_pairs.append(("", addr.lower()))

    # Deduplicate within this email, keep first display_name per address
    seen: dict[str, str] = {}
    result: list[tuple[str, str]] = []
    for name, addr in raw_pairs:
        if addr not in seen:
            seen[addr] = name
            result.append((name, addr))
        elif not seen[addr] and name:
            seen[addr] = name
            # Update existing entry
            for i, (n, a) in enumerate(result):
                if a == addr:
                    result[i] = (name, addr)
                    break

    return result


def parse_and_store_contacts(
    session: Session,
    account_id: int,
    email_id: int,
    raw_bytes: bytes,
    date_seen: Optional[datetime],
) -> int:
    """Parse raw email bytes and upsert contacts. Returns count of addresses found."""
    try:
        msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)
    except Exception as exc:
        log.warning("Failed to parse email %d: %s", email_id, exc)
        return 0

    addresses = extract_addresses(msg)
    if not addresses:
        return 0

    if date_seen is None:
        date_seen = datetime.now(timezone.utc)

    source_info = {"email_id": email_id}

    for display_name, addr in addresses:
        try:
            repo.upsert_contact(
                session,
                account_id=account_id,
                email_address=addr,
                display_name=display_name or None,
                seen_at=date_seen,
                source_info=source_info,
            )
        except Exception as exc:
            log.warning("Failed to upsert contact %s: %s", addr, exc)

    return len(addresses)

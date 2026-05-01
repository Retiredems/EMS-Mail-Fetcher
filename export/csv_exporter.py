"""Export contacts to CSV."""

import csv
from pathlib import Path
from typing import Sequence

from db.models import Contact


def export_contacts_csv(contacts: Sequence[Contact], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["email", "display_name", "occurrence_count", "first_seen", "last_seen", "account_id"])
        for c in contacts:
            writer.writerow([
                c.email_address,
                c.display_name or "",
                c.occurrence_count,
                c.first_seen_at.isoformat() if c.first_seen_at else "",
                c.last_seen_at.isoformat() if c.last_seen_at else "",
                c.account_id,
            ])
    return len(contacts)

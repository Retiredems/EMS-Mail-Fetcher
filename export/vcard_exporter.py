"""Export contacts to vCard 3.0 (.vcf)."""

from pathlib import Path
from typing import Sequence

from db.models import Contact


def export_contacts_vcard(contacts: Sequence[Contact], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for c in contacts:
        name = c.display_name or c.email_address
        lines.append("BEGIN:VCARD")
        lines.append("VERSION:3.0")
        lines.append(f"FN:{name}")
        lines.append(f"EMAIL;TYPE=INTERNET:{c.email_address}")
        if c.occurrence_count:
            lines.append(f"NOTE:Occurrence count: {c.occurrence_count}")
        lines.append("END:VCARD")
        lines.append("")

    output_path.write_text("\r\n".join(lines), encoding="utf-8")
    return len(contacts)

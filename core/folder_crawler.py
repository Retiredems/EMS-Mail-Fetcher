"""Recursively lists all folders for an account and upserts them in the DB."""

from __future__ import annotations

import logging

from db.database import get_session
from db.models import Folder
from db import repository as repo

log = logging.getLogger(__name__)

SUGGEST_EXCLUDE = {"Trash", "Deleted", "Junk", "Spam", "Deleted Items", "Drafts"}


def crawl_and_store_folders(account_id: int, client) -> list[dict]:
    """
    Use the connected client to list all folders, store in DB, return list of dicts.
    Each dict: {id, name, full_path, is_excluded}
    """
    raw_folders = client.list_folders()
    result = []

    with get_session() as session:
        for f in raw_folders:
            full_path = f["full_path"]
            name = f["name"]
            is_suggested_exclude = name in SUGGEST_EXCLUDE or any(
                ex in name for ex in SUGGEST_EXCLUDE
            )

            folder_obj = repo.upsert_folder(
                session,
                account_id=account_id,
                name=name,
                full_path=full_path,
            )
            if is_suggested_exclude and folder_obj.status == "pending":
                folder_obj.is_excluded = True

            result.append({
                "id": folder_obj.id,
                "name": name,
                "full_path": full_path,
                "is_excluded": folder_obj.is_excluded,
                "flags": f.get("flags", []),
            })

    return result


def set_folder_exclusion(folder_id: int, excluded: bool) -> None:
    with get_session() as session:
        folder = session.get(Folder, folder_id)
        if folder:
            folder.is_excluded = excluded

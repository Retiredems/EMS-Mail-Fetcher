"""CRUD operations for all models."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from db.models import Account, Contact, Email, Folder

log = logging.getLogger(__name__)


# ── Account ──────────────────────────────────────────────────────────────────

def get_all_accounts(session: Session) -> list[Account]:
    return session.query(Account).order_by(Account.created_at).all()


def get_account_by_id(session: Session, account_id: int) -> Optional[Account]:
    return session.get(Account, account_id)


def get_account_by_email(session: Session, email: str) -> Optional[Account]:
    return session.query(Account).filter_by(email=email.lower()).first()


def create_account(session: Session, **kwargs) -> Account:
    if "email" in kwargs:
        kwargs["email"] = kwargs["email"].lower()
    account = Account(**kwargs)
    session.add(account)
    session.flush()
    return account


def update_account(session: Session, account: Account, **kwargs) -> Account:
    for k, v in kwargs.items():
        setattr(account, k, v)
    session.flush()
    return account


def delete_account(session: Session, account: Account) -> None:
    session.delete(account)
    session.flush()


# ── Folder ───────────────────────────────────────────────────────────────────

def get_folders_for_account(session: Session, account_id: int) -> list[Folder]:
    return (
        session.query(Folder)
        .filter_by(account_id=account_id)
        .order_by(Folder.full_path)
        .all()
    )


def get_folder_by_path(session: Session, account_id: int, full_path: str) -> Optional[Folder]:
    return session.query(Folder).filter_by(account_id=account_id, full_path=full_path).first()


def upsert_folder(
    session: Session,
    account_id: int,
    name: str,
    full_path: str,
    parent_folder_id: Optional[int] = None,
) -> Folder:
    folder = get_folder_by_path(session, account_id, full_path)
    if folder is None:
        folder = Folder(
            account_id=account_id,
            name=name,
            full_path=full_path,
            parent_folder_id=parent_folder_id,
        )
        session.add(folder)
        session.flush()
    return folder


def update_folder_progress(
    session: Session,
    folder: Folder,
    fetched: int,
    total: Optional[int] = None,
    status: Optional[str] = None,
    last_uid: Optional[int] = None,
) -> None:
    folder.fetched_emails = fetched
    if total is not None:
        folder.total_emails = total
    if status is not None:
        folder.status = status
    if last_uid is not None:
        folder.last_uid = last_uid
    session.flush()


# ── Email ────────────────────────────────────────────────────────────────────

def email_uid_exists(session: Session, account_id: int, folder_id: int, uid: int) -> bool:
    return (
        session.query(Email)
        .filter_by(account_id=account_id, folder_id=folder_id, uid=uid)
        .count()
        > 0
    )


def email_message_id_exists(session: Session, account_id: int, message_id: str) -> bool:
    return (
        session.query(Email)
        .filter_by(account_id=account_id, message_id=message_id)
        .count()
        > 0
    )


def create_email(session: Session, **kwargs) -> Email:
    email_obj = Email(**kwargs)
    session.add(email_obj)
    session.flush()
    return email_obj


def mark_email_parsed(session: Session, email_obj: Email) -> None:
    email_obj.is_parsed = True
    session.flush()


def get_emails_for_account(
    session: Session,
    account_id: int,
    limit: int = 500,
    offset: int = 0,
    search: Optional[str] = None,
) -> list[Email]:
    q = session.query(Email).filter_by(account_id=account_id)
    if search:
        q = q.filter(Email.subject.ilike(f"%{search}%"))
    return q.order_by(Email.date_sent.desc()).limit(limit).offset(offset).all()


def count_emails_for_account(session: Session, account_id: int) -> int:
    return session.query(Email).filter_by(account_id=account_id).count()


def count_all_emails(session: Session) -> int:
    return session.query(Email).count()


# ── Contact ──────────────────────────────────────────────────────────────────

def upsert_contact(
    session: Session,
    account_id: int,
    email_address: str,
    display_name: Optional[str],
    seen_at: datetime,
    source_info: Optional[dict] = None,
) -> Contact:
    addr = email_address.lower().strip()
    contact = (
        session.query(Contact)
        .filter_by(account_id=account_id, email_address=addr)
        .first()
    )

    if contact is None:
        contact = Contact(
            account_id=account_id,
            email_address=addr,
            display_name=display_name or "",
            first_seen_at=seen_at,
            last_seen_at=seen_at,
            occurrence_count=1,
            sources_json=json.dumps([source_info] if source_info else []),
        )
        session.add(contact)
    else:
        contact.occurrence_count += 1
        if display_name and not contact.display_name:
            contact.display_name = display_name
        if contact.first_seen_at is None or seen_at < contact.first_seen_at:
            contact.first_seen_at = seen_at
        if contact.last_seen_at is None or seen_at > contact.last_seen_at:
            contact.last_seen_at = seen_at
        if source_info:
            sources = contact.sources
            sources.append(source_info)
            contact.sources = sources[-100:]  # cap stored sources

    session.flush()
    return contact


def get_contacts_for_account(
    session: Session,
    account_id: int,
    search: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0,
) -> list[Contact]:
    q = session.query(Contact).filter_by(account_id=account_id)
    if search:
        q = q.filter(
            (Contact.email_address.ilike(f"%{search}%"))
            | (Contact.display_name.ilike(f"%{search}%"))
        )
    return q.order_by(Contact.occurrence_count.desc()).limit(limit).offset(offset).all()


def get_all_contacts(
    session: Session,
    search: Optional[str] = None,
    limit: int = 5000,
    offset: int = 0,
) -> list[Contact]:
    q = session.query(Contact)
    if search:
        q = q.filter(
            (Contact.email_address.ilike(f"%{search}%"))
            | (Contact.display_name.ilike(f"%{search}%"))
        )
    return q.order_by(Contact.occurrence_count.desc()).limit(limit).offset(offset).all()


def count_all_contacts(session: Session) -> int:
    return session.query(Contact).count()

"""SQLAlchemy ORM models."""

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    protocol: Mapped[str] = mapped_column(String(32), nullable=False)  # IMAP/POP3/Exchange/Gmail_OAuth/Outlook_OAuth
    server: Mapped[Optional[str]] = mapped_column(String(255))
    port: Mapped[Optional[int]] = mapped_column(Integer)
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    username: Mapped[Optional[str]] = mapped_column(String(320))
    encrypted_password: Mapped[Optional[str]] = mapped_column(Text)
    oauth_token_json: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="idle")
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    folders: Mapped[list["Folder"]] = relationship(
        "Folder", back_populates="account", cascade="all, delete-orphan"
    )
    emails: Mapped[list["Email"]] = relationship(
        "Email", back_populates="account", cascade="all, delete-orphan"
    )
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact", back_populates="account", cascade="all, delete-orphan"
    )


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    full_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    parent_folder_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("folders.id"))
    total_emails: Mapped[int] = mapped_column(Integer, default=0)
    fetched_emails: Mapped[int] = mapped_column(Integer, default=0)
    last_uid: Mapped[Optional[int]] = mapped_column(BigInteger)  # for incremental sync
    status: Mapped[str] = mapped_column(String(32), default="pending")
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)

    account: Mapped["Account"] = relationship("Account", back_populates="folders")
    emails: Mapped[list["Email"]] = relationship(
        "Email", back_populates="folder", cascade="all, delete-orphan"
    )
    children: Mapped[list["Folder"]] = relationship("Folder", back_populates="parent")
    parent: Mapped[Optional["Folder"]] = relationship(
        "Folder", back_populates="children", remote_side="Folder.id"
    )

    __table_args__ = (
        UniqueConstraint("account_id", "full_path", name="uq_folder_account_path"),
    )


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False)
    folder_id: Mapped[int] = mapped_column(Integer, ForeignKey("folders.id"), nullable=False)
    message_id: Mapped[Optional[str]] = mapped_column(String(998))
    uid: Mapped[Optional[int]] = mapped_column(BigInteger)
    subject: Mapped[Optional[str]] = mapped_column(Text)
    from_address: Mapped[Optional[str]] = mapped_column(String(320))
    date_sent: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    raw_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    raw_eml_path: Mapped[Optional[str]] = mapped_column(Text)
    is_parsed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    account: Mapped["Account"] = relationship("Account", back_populates="emails")
    folder: Mapped["Folder"] = relationship("Folder", back_populates="emails")

    __table_args__ = (
        UniqueConstraint("account_id", "folder_id", "uid", name="uq_email_account_folder_uid"),
    )


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False)
    email_address: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(500))
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    sources_json: Mapped[str] = mapped_column(Text, default="[]")

    account: Mapped["Account"] = relationship("Account", back_populates="contacts")

    __table_args__ = (
        UniqueConstraint("account_id", "email_address", name="uq_contact_account_email"),
    )

    @property
    def sources(self) -> list:
        try:
            return json.loads(self.sources_json)
        except Exception:
            return []

    @sources.setter
    def sources(self, value: list) -> None:
        self.sources_json = json.dumps(value)

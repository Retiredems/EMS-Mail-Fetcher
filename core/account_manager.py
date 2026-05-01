"""Account storage with Fernet encryption for credentials."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from config.settings import KEY_FILE
from db.database import get_session
from db import repository as repo

log = logging.getLogger(__name__)

_fernet: Optional[Fernet] = None


def _load_or_create_key() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    if KEY_FILE.exists():
        key = KEY_FILE.read_bytes()
    else:
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
        # Restrictive permissions on Unix
        try:
            os.chmod(KEY_FILE, 0o600)
        except OSError:
            pass
        log.info("Generated new Fernet encryption key at %s", KEY_FILE)

    _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> str:
    f = _load_or_create_key()
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    f = _load_or_create_key()
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError("Failed to decrypt credential — key may have changed")


def add_account(
    email: str,
    protocol: str,
    display_name: str = "",
    server: str = "",
    port: int = 993,
    use_ssl: bool = True,
    username: str = "",
    password: str = "",
    oauth_token: Optional[dict] = None,
) -> int:
    """Create a new account record; returns the new account ID."""
    encrypted_pw = encrypt(password) if password else None
    oauth_json = json.dumps(oauth_token) if oauth_token else None

    with get_session() as session:
        existing = repo.get_account_by_email(session, email)
        if existing:
            raise ValueError(f"Account {email} already exists")

        account = repo.create_account(
            session,
            email=email,
            display_name=display_name or email,
            protocol=protocol,
            server=server,
            port=port,
            use_ssl=use_ssl,
            username=username or email,
            encrypted_password=encrypted_pw,
            oauth_token_json=oauth_json,
        )
        return account.id


def update_account_credentials(
    account_id: int,
    password: Optional[str] = None,
    oauth_token: Optional[dict] = None,
) -> None:
    with get_session() as session:
        account = repo.get_account_by_id(session, account_id)
        if account is None:
            raise ValueError(f"Account ID {account_id} not found")
        updates: dict = {}
        if password is not None:
            updates["encrypted_password"] = encrypt(password)
        if oauth_token is not None:
            updates["oauth_token_json"] = json.dumps(oauth_token)
        repo.update_account(session, account, **updates)


def update_account_status(account_id: int, status: str) -> None:
    with get_session() as session:
        account = repo.get_account_by_id(session, account_id)
        if account:
            repo.update_account(session, account, status=status)


def get_account_password(account_id: int) -> Optional[str]:
    with get_session() as session:
        account = repo.get_account_by_id(session, account_id)
        if account and account.encrypted_password:
            return decrypt(account.encrypted_password)
        return None


def get_account_oauth_token(account_id: int) -> Optional[dict]:
    with get_session() as session:
        account = repo.get_account_by_id(session, account_id)
        if account and account.oauth_token_json:
            return json.loads(account.oauth_token_json)
        return None


def save_account_oauth_token(account_id: int, token: dict) -> None:
    with get_session() as session:
        account = repo.get_account_by_id(session, account_id)
        if account:
            repo.update_account(session, account, oauth_token_json=json.dumps(token))


def delete_account(account_id: int) -> None:
    with get_session() as session:
        account = repo.get_account_by_id(session, account_id)
        if account:
            repo.delete_account(session, account)


def list_accounts() -> list[dict]:
    with get_session() as session:
        accounts = repo.get_all_accounts(session)
        return [
            {
                "id": a.id,
                "email": a.email,
                "display_name": a.display_name,
                "protocol": a.protocol,
                "server": a.server,
                "port": a.port,
                "use_ssl": a.use_ssl,
                "username": a.username,
                "status": a.status,
                "last_synced_at": a.last_synced_at,
                "created_at": a.created_at,
            }
            for a in accounts
        ]


def import_accounts_from_file(file_path: str) -> list[dict]:
    """
    Parse a text file of email:password lines and add each as an account.
    Lines starting with # are skipped. Blank lines are skipped.
    Returns a list of result dicts: {email, status, message}.
    """
    results = []
    path = Path(file_path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Support both comma and colon as separator
        # Try comma first (passwords rarely contain commas)
        if "," in line:
            email, password = line.split(",", 1)
        elif ":" in line:
            email, password = line.split(":", 1)
        else:
            results.append({"email": line, "status": "skipped", "message": "No separator found (use , or :)"})
            continue
        email = email.strip().lower()
        password = password.strip()

        if not email or "@" not in email:
            results.append({"email": line, "status": "skipped", "message": "Invalid email address"})
            continue

        domain = email.split("@", 1)[1]
        preset = get_preset_for_domain(domain) or {}
        imap = preset.get("imap", {})
        oauth_type = preset.get("oauth")

        # OAuth accounts cannot be imported from a password file
        if oauth_type and not imap:
            results.append({
                "email": email,
                "status": "skipped",
                "message": f"Provider requires OAuth — add {email} manually",
            })
            continue

        server = imap.get("server", f"imap.{domain}")
        port = imap.get("port", 993)
        use_ssl = imap.get("ssl", True)
        protocol = "IMAP"

        try:
            add_account(
                email=email,
                protocol=protocol,
                display_name=email,
                server=server,
                port=port,
                use_ssl=use_ssl,
                username=email,
                password=password,
            )
            results.append({"email": email, "status": "added", "message": f"{server}:{port}"})
        except ValueError as exc:
            # Already exists
            results.append({"email": email, "status": "duplicate", "message": str(exc)})
        except Exception as exc:
            results.append({"email": email, "status": "error", "message": str(exc)})

    return results


def load_server_presets() -> dict:
    from config.settings import SERVER_PRESETS_FILE
    if SERVER_PRESETS_FILE.exists():
        return json.loads(SERVER_PRESETS_FILE.read_text(encoding="utf-8"))
    return {}


def get_preset_for_domain(domain: str) -> Optional[dict]:
    presets = load_server_presets()
    return presets.get(domain.lower())


def lookup_domain_preset(email_address: str) -> Optional[dict]:
    """Return server preset dict for the email domain, or None."""
    if "@" not in email_address:
        return None
    domain = email_address.split("@", 1)[1].lower()
    preset = get_preset_for_domain(domain)
    if preset:
        return preset

    # Try MX-based lookup as fallback
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "MX")
        mx = str(sorted(answers, key=lambda r: r.preference)[0].exchange).rstrip(".")
        return {
            "imap": {"server": f"imap.{domain}", "port": 993, "ssl": True},
            "pop3": {"server": f"pop.{domain}", "port": 995, "ssl": True},
            "_mx": mx,
        }
    except Exception:
        return None

"""License validation for EMS Mail Fetcher — mirrors the bot's Node.js logic."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# Must match the bot's SECRET exactly
_SECRET = "EMS_SECRET_KEY"

# Store license in a hidden folder in the user's home directory
if sys.platform == "win32":
    _LICENSE_FILE = Path.home() / "AppData" / "Roaming" / "EMS Fetcher" / "license.json"
else:
    _LICENSE_FILE = Path.home() / ".ems_fetcher" / "license.json"

_LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)

# License server (same server as EMS Mailer)
LICENSE_SERVER_URLS = [
    "http://191.96.25.58:3000",
]


def _get_machine_id() -> str:
    """Return the most stable available system identifier for this machine."""
    import subprocess

    if sys.platform == "darwin":
        try:
            out = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5
            ).stdout
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    parts = line.split('"')
                    if len(parts) >= 4:
                        return parts[-2]
        except Exception:
            pass

    elif sys.platform == "win32":
        try:
            out = subprocess.run(
                ["wmic", "csproduct", "get", "UUID", "/value"],
                capture_output=True, text=True, timeout=5
            ).stdout
            for line in out.splitlines():
                if "UUID=" in line:
                    uid = line.split("=", 1)[1].strip()
                    if uid:
                        return uid
        except Exception:
            pass

    else:
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                content = Path(p).read_text().strip()
                if content:
                    return content
            except Exception:
                pass

    # Fallback: stable components — exclude platform.processor() which varies
    return ":".join([str(uuid.getnode()), platform.node(), platform.system(), platform.machine()])


def get_hwid() -> str:
    """Return a stable SHA-256 fingerprint for this machine."""
    return hashlib.sha256(_get_machine_id().encode("utf-8")).hexdigest()


def _load_license() -> Optional[dict]:
    try:
        return json.loads(_LICENSE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_license(data: dict) -> None:
    _LICENSE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def check_license() -> bool:
    """Return True if the stored license is valid for this machine."""
    lic = _load_license()
    if not lic:
        return False

    expiry = lic.get("expiry", 0)
    if time.time() * 1000 > expiry:
        return False

    hwids = lic.get("hwids") or ([lic["hwid"]] if lic.get("hwid") else [])
    if not hwids:
        return False

    # Verify hash integrity against the anchor (first) HWID
    anchor = hwids[0]
    raw = f"{anchor}:{expiry}:{_SECRET}"
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if expected != lic.get("hash"):
        return False  # tampered or invalid

    my_hwid = get_hwid()
    if my_hwid in hwids:
        return True

    # HWID changed (e.g. algorithm update) but license is cryptographically
    # valid. Auto-register current HWID locally so user never re-activates.
    max_devices = lic.get("maxDevices", 1)
    if len(hwids) < max_devices:
        hwids.append(my_hwid)
        lic["hwids"] = hwids
        _save_license(lic)
        return True

    # Replace the last non-anchor HWID with current machine (same-machine
    # re-key after OS reinstall or algorithm change, single-device license)
    if len(hwids) == 1:
        lic["hwids"] = [my_hwid]
        lic["hash"] = hashlib.sha256(
            f"{my_hwid}:{expiry}:{_SECRET}".encode()
        ).hexdigest()
        _save_license(lic)
        return True

    return False


def get_license_info() -> dict:
    """Return dict with valid, name, days_left (-1 = lifetime)."""
    lic = _load_license()
    if not lic or not check_license():
        return {"valid": False, "name": None, "days_left": 0}

    expiry = lic.get("expiry", 0)
    ms_left = expiry - time.time() * 1000
    days_left = -1 if expiry > (time.time() + 99 * 365 * 86400) * 1000 else max(0, int(ms_left / 86400000))

    return {
        "valid": True,
        "name": lic.get("name", "User"),
        "days_left": days_left,
    }


def activate_license(input_key: str, server_license: dict) -> dict:
    """Validate the key against the server license and store it locally."""
    input_key = input_key.strip().upper()

    import re
    if not re.match(r"^EMF-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}$", input_key):
        return {"success": False, "message": "Invalid key format — expected EMF-XXXX-XXXX-XXXX-XXXX"}

    server_key = server_license.get("key", "").strip().upper()
    if input_key != server_key:
        return {"success": False, "message": "License key does not match"}

    expiry = server_license.get("expiry", 0)
    if time.time() * 1000 > expiry:
        return {"success": False, "message": "License has expired"}

    hwid = get_hwid()

    # Support both hwids array (multi-device) and legacy single hwid
    hwids = server_license.get("hwids") or ([server_license["hwid"]] if server_license.get("hwid") else [])
    if hwid not in hwids:
        return {"success": False, "message": "License is not registered for this device"}

    # Hash verified against the first/anchor HWID
    anchor = hwids[0]
    raw = f"{anchor}:{expiry}:{_SECRET}"
    expected_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if expected_hash != server_license.get("hash"):
        return {"success": False, "message": "License integrity check failed"}

    # Save with full hwids array so multi-device check works offline too
    server_license["hwids"] = hwids
    _save_license(server_license)
    return {"success": True, "name": server_license.get("name", "User")}


def fetch_and_activate(input_key: str) -> dict:
    """Contact the license server, validate, and store the license."""
    import urllib.request
    import urllib.parse

    hwid = get_hwid()
    params = urllib.parse.urlencode({"hwid": hwid})

    for base in LICENSE_SERVER_URLS:
        try:
            url = f"{base}/get-fetcher-license?{params}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if not data.get("success"):
                return {"success": False, "message": data.get("message", "No license found for this device")}
            return activate_license(input_key, data["license"])
        except Exception as exc:
            continue

    return {"success": False, "message": "Could not reach license server. Check your internet connection."}

<p align="center">
  <img src="assets/icon.png" alt="EMS Mail Fetcher" width="96"/>
</p>

<h1 align="center">EMS Mail Fetcher</h1>

<p align="center">
  <strong>Precision Inbox Intelligence</strong><br/>
  A professional desktop tool for bulk email account testing, archiving, and exporting — built for RDP power users, mailer operators, and email marketers.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-blue?style=flat-square"/>
  <img src="https://img.shields.io/badge/Protocol-IMAP%20%7C%20POP3%20%7C%20OAuth%20%7C%20Exchange-green?style=flat-square"/>
  <img src="https://img.shields.io/badge/License-Commercial-orange?style=flat-square"/>
  <img src="https://img.shields.io/github/v/release/Retiredems/EMS-Mail-Fetcher?style=flat-square"/>
</p>

---

## What Is EMS Mail Fetcher?

EMS Mail Fetcher is a native desktop application that lets you load a list of email accounts, test them in parallel, fetch and archive messages, and export results — all without touching a browser or writing a single line of code.

Built for **RDP environments**, **email marketers**, and **mailer operators** who need to process hundreds of accounts fast.

---

## Key Features

### Multi-Protocol Support
| Protocol | Auth Method | Notes |
|----------|-------------|-------|
| IMAP / IMAPS | Password | Port 143 (STARTTLS) or 993 (SSL) |
| POP3 / POP3S | Password | Port 110 or 995 |
| Gmail | OAuth 2.0 | No app password needed |
| Outlook / Office 365 | OAuth 2.0 (MSAL) | Works with modern auth |
| Exchange (EWS) | Password / NTLM | On-premise + hosted |

### Bulk Account Loading
- Load accounts from `.txt` or `.csv` — `email:password` format
- Auto-detect IMAP/SMTP server via **DNS MX lookup** (no manual config needed)
- Pre-configured server presets for Gmail, Outlook, Yahoo, and more

### Parallel Fetch Engine
- **5 worker threads** by default (configurable up to 20)
- Per-account status tracking: `Connecting → Running → Finished / Error`
- Auto-reconnect with exponential back-off (up to 3 retries)
- Configurable connection timeout (30 s default)

### Email Archiving
- SQLite local database — no cloud required
- Full email storage: headers, body, attachments
- Folder-aware: fetch Inbox, Sent, custom folders
- Date-range and UID-based filtering to avoid re-fetching

### Export Options
| Format | Contents |
|--------|----------|
| CSV | Sender, recipient, subject, date, body snippet |
| Excel (.xlsx) | Same as CSV, formatted with openpyxl |
| .eml | Raw RFC-2822 message files |
| vCard (.vcf) | Extracted contacts from address fields |

### Privacy & Security
- Passwords encrypted at rest using **Fernet (AES-128-GCM)**
- No passwords ever leave your machine
- Hardware-tied license (machine UUID — not dependent on software state)
- Self-healing activation: survives Python upgrades and system updates without re-activating

### Proxy Support
- SOCKS5 proxy with optional username/password
- Applied to all IMAP and POP3 connections
- Configure once in Settings — persists across sessions

### Dark & Light Themes
- Premium dark UI (default) with glowing teal accents
- Clean light theme — switch instantly from the toolbar
- High-DPI / Retina-ready

### Built-in Update Checker
- Checks GitHub releases on every launch (silent, no interruption)
- One-click update notification banner when a new version is available

---

## Screenshots

> _Add screenshots here after first launch_

---

## Installation

### Windows (.exe Installer)

1. Download `EMS_Mail_Fetcher_Windows.zip` from the [latest release](../../releases/latest)
2. Extract the zip
3. Run `EMS_Mail_Fetcher.exe`
4. Enter your license key on first launch

> **RDP users:** Copy the extracted folder to your RDP server and run from there. No installer needed — it is fully portable.

### macOS (.app Bundle)

1. Download `EMS_Mail_Fetcher_macOS.zip` from the [latest release](../../releases/latest)
2. Extract and drag `EMS Mail Fetcher.app` to your Applications folder
3. Right-click → Open on first launch (to bypass Gatekeeper on unsigned builds)
4. Enter your license key

---

## Getting a License

EMS Mail Fetcher is a **commercial product**. Licenses are sold per device and are hardware-tied (no cloud check-in required after activation).

- **[Get EMS Mailer →](https://github.com/Retiredems/Ems-Mailer/releases/latest)** — purchase includes a license key for EMS Mail Fetcher

Each license is valid for a single machine. If you reinstall Windows or move to a new RDP server, your license transfers automatically — no re-activation needed as long as the hardware UUID is detected correctly.

---

## Account File Format

Load a plain text or CSV file with one account per line:

```
email@example.com:password123
another@gmail.com:mypassword
user@outlook.com:securepass
```

The app will auto-detect the mail server for each domain via DNS MX lookup. You can override the server in Settings if needed.

---

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Thread count | 5 | Parallel fetch workers |
| Connection timeout | 30 s | TCP + SSL handshake deadline |
| Theme | Dark | Dark or Light |
| Proxy | Disabled | SOCKS5 host:port (optional) |
| Export directory | `~/Documents` | Where exports are saved |

---

## System Requirements

| | Windows | macOS |
|-|---------|-------|
| OS | Windows 10 / 11 (64-bit) | macOS 11+ (Intel or Apple Silicon) |
| RAM | 256 MB minimum | 256 MB minimum |
| Disk | 150 MB | 150 MB |
| Network | Required | Required |

> Works on Windows Server 2016/2019/2022 — including RDP / VPS environments.

---

## Build From Source

If you want to build the app yourself:

```bash
git clone https://github.com/Retiredems/EMS-Mail-Fetcher.git
cd EMS-Mail-Fetcher/email_archiver
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py                  # run from source
```

To build a standalone executable:

```bash
pyinstaller email_archiver.spec --clean --noconfirm
# Output: dist/EMS_Mail_Fetcher/  (Windows)
#         dist/EMS Mail Fetcher.app  (macOS)
```

CI builds for both platforms run automatically via GitHub Actions on every `v*` tag push.

---

## Changelog

### v1.0.0
- Initial public release
- IMAP, POP3, Gmail OAuth, Outlook OAuth, Exchange (EWS) support
- Parallel fetch engine (5 threads default)
- CSV, Excel, .eml, vCard export
- Dark / light theme
- SOCKS5 proxy support
- Hardware-tied license with self-healing activation
- Auto-update checker via GitHub releases
- Windows (.exe) and macOS (.app) builds via GitHub Actions

---

## Support

Open an issue on GitHub for bug reports and feature requests.

---

<p align="center">
  Built with precision by <strong>Retiredems</strong> &nbsp;·&nbsp; Powered by PyQt6
</p>

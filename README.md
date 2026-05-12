<!-- ems-callout -->
> **v1.3.1 — refreshed brand and a polished activation flow.** Same software, sharper edges. [→ Download the latest build](https://github.com/Retiredems/EMS-Mail-Fetcher/releases/latest)
<!-- ems-callout -->
<p align="center">
  <img width="837" height="558" alt="Screenshot 2026-05-02 at 02 27 54" src="https://github.com/user-attachments/assets/26537010-399e-4645-af16-46281e285b10" />

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

Built for **email marketers**, **mailer operators**, and **power users** who need to process hundreds of accounts fast — on any Windows or macOS machine.

---

## Screenshots

<img width="1062" height="629" alt="Screenshot 2026-05-02 at 15 19 55" src="https://github.com/user-attachments/assets/7a1027ce-eb0e-4ae6-8ce6-58c5f66b00cc" />


<img width="1063" height="631" alt="Screenshot 2026-05-02 at 15 31 07" src="https://github.com/user-attachments/assets/cf734ff3-c67c-4089-85bb-b56a6b6127c4" />

<img width="1060" height="632" alt="Screenshot 2026-05-02 at 15 20 14" src="https://github.com/user-attachments/assets/6b9846a2-d6d4-41ab-9bf1-86f0bd741abc" />

<img width="2126" height="1276" alt="new ems mail fetcher" src="https://github.com/user-attachments/assets/1b1d4d54-a378-4cfc-87c0-114370fc5556" />



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
- Load accounts from `.txt` or `.csv` — `email:password` format (UTF-8 and UTF-16 BOM files supported)
- Auto-detect IMAP/SMTP server via **DNS MX lookup** (no manual config needed)
- **223-entry server preset library** — Gmail, Yahoo (20+ TLDs), Outlook/Live/Hotmail (25+ locales), Russian, Chinese, Korean, Japanese, Brazilian, German, French, Italian, US ISPs, privacy providers, and more
- Automatic fallback: if no preset matches, tries the domain itself as the IMAP/POP3 host
- Multi-server retry — each preset lists alternate hostnames tried in order before giving up

### Parallel Fetch Engine
- **5 worker threads** by default (configurable up to 20)
- Per-account status tracking: `Connecting → Running → Finished / Error`
- **Login-only mode** — verify credentials without downloading any mail
- **Date range filter (From / To)** — server-side IMAP `SINCE`/`BEFORE` filtering; saves bandwidth
- **Keyword search** — IMAP `TEXT` search applied at the server before downloading
- **Error codes in status column** — `[AUTHENTICATIONFAILED]`, `[TIMEOUT]`, `[SSL_ERR]`, `[DNS_ERR]`, `[REFUSED]`
- Auto-reconnect with exponential back-off (up to 3 retries)
- Short-username fallback — retries with `user` if `user@domain.com` fails auth
- Non-English folder names decoded correctly (Russian, Chinese, Arabic, Japanese)
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
- Supports `socks5://user:pass@ip:port` and `ip:port,user,pass` formats
- Applied to all IMAP and POP3 connections
- Configure once in Settings — persists across sessions

### Dark & Light Themes
- Premium dark UI (default) with glowing teal accents
- Clean light theme — switch instantly from the toolbar
- High-DPI / Retina-ready

### Built-in Update Checker
- Checks for new versions on every launch (silent, no interruption)
- One-click update notification banner when a new version is available

---

## Installation

### Windows

1. Download `EMS_Mail_Fetcher_Windows.zip` from the [latest release](../../releases/latest)
2. Extract the zip
3. Run `EMS_Mail_Fetcher.exe`
4. Enter your license key on first launch

> No installation required — fully portable. Works on any Windows desktop, laptop, server, VPS, or RDP environment.

### macOS

1. Download `EMS_Mail_Fetcher_macOS.zip` from the [latest release](../../releases/latest)
2. Extract and drag `EMS Mail Fetcher.app` to your Applications folder
3. Right-click → Open on first launch (Gatekeeper bypass for unsigned builds)
4. Enter your license key

---

## Getting a License

EMS Mail Fetcher is a **commercial product**. Licenses are sold per device and are hardware-tied — no cloud check-in required after activation.

Contact via Telegram to purchase a license key.

👉 **Telegram: [@retiredems](https://t.me/retiredems)**
🤖 **Bot: [@emsmailerbot](https://t.me/emsmailerbot)**
Each license is valid for a single machine. If you reinstall Windows or move to a new RDP server, your license transfers automatically — no re-activation needed.

---

## Account File Format

Load a plain text or CSV file with one account per line:

```
email@example.com:password123
another@gmail.com:mypassword
user@outlook.com:securepass
```

The app auto-detects the mail server for each domain via DNS MX lookup. You can override the server in Settings if needed.

---

## System Requirements

| | Windows | macOS |
|-|---------|-------|
| OS | Windows 10 / 11 (64-bit) | macOS 11+ (Intel or Apple Silicon) |
| RAM | 256 MB minimum | 256 MB minimum |
| Disk | 150 MB | 150 MB |
| Network | Required | Required |

> Works on any Windows 10 / 11 desktop or laptop, and Windows Server 2016 / 2019 / 2022 including VPS and RDP environments.

---

## Changelog

### v1.1.0 — May 2026

#### Server Coverage
- **223-entry server preset library** — Yahoo (20+ TLDs), Live/Hotmail (25+ locales), Russian (Mail.ru, Yandex, Rambler), Chinese (163, 126, QQ, Sina, Sohu), Korean, Japanese, Brazilian, German, French, Italian, UK/Canadian/Australian, Polish, Czech, Israeli, Turkish, Scandinavian, major US ISPs, and privacy providers (ProtonMail, Tutanota, Fastmail, Zoho, and more)
- **`#domain#` auto-fallback** — any unrecognized domain automatically attempts IMAP/POP3 using the domain itself as the hostname — nothing gets skipped
- **Multi-server retry** — alternate hostnames tried in order before reporting failure
- **Live MX record lookup** — DNS resolved before falling back to hostname patterns

#### Authentication
- **Short-username fallback** — retries with `user` if `user@domain.com` fails (required by many ISP and corporate servers)
- **Login-only mode** — verify credentials across hundreds of accounts without downloading mail; each reports "Login OK ✓" or the exact error code

#### Filtering
- **Date range (From / To)** — server-side IMAP `SINCE`/`BEFORE` filtering; leave blank to fetch everything
- **Keyword search** — IMAP `TEXT` search at the server before downloading saves bandwidth and time

#### Reliability
- **Non-English folder names** — IMAP modified UTF-7 fully decoded (Russian, Chinese, Arabic, Japanese)
- **BOM-safe file loading** — UTF-8/UTF-16 BOM in email:pass files handled correctly on all platforms
- **Error codes in status column** — `[AUTHENTICATIONFAILED]`, `[TIMEOUT]`, `[SSL_ERR]`, `[DNS_ERR]`, `[REFUSED]` shown per account
- **Auto-reconnect** — dropped connections mid-fetch re-established silently (up to 3 retries)
- **AOL & slow-server fix** — per-connection deadline prevents stuck threads blocking the whole run
- **Exchange (EWS) crash fixed** — Exchange accounts now use a dedicated code path

#### UI
- **Comma-format proxy** — accepts `ip:port,user,pass` in addition to URL format
- **Right-click Copy Domain / Copy Server** — new context-menu actions on account rows
- **From / To date fields + keyword bar** — dedicated filter row below the toolbar

### v1.0.0
- Initial public release
- IMAP, POP3, Gmail OAuth, Outlook OAuth, Exchange (EWS) support
- Parallel fetch engine with 5 worker threads
- CSV, Excel, .eml, vCard export
- Dark / light theme
- SOCKS5 proxy support
- Hardware-tied license with self-healing activation
- Built-in update checker

---

## Support

Open an issue on GitHub for bug reports and feature requests.

---

<p align="center">
  Built with precision by <strong>Retiredems</strong> &nbsp;·&nbsp; Powered by PyQt6
</p>

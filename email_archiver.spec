# PyInstaller spec — EMS Mail Fetcher
# Build with: pyinstaller email_archiver.spec --clean --noconfirm

import sys
from pathlib import Path

a = Analysis(
    ['main.py'],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=[
        ('config/server_presets.json', 'config'),
        ('ui/styles.qss',             'ui'),
        ('ui/styles_light.qss',       'ui'),
        ('ui/check_white.svg',        'ui'),
    ],
    hiddenimports=[
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.ext.declarative',
        'email.mime.text',
        'email.mime.multipart',
        'google.auth.transport.requests',
        'google_auth_oauthlib.flow',
        'googleapiclient.discovery',
        'msal',
        'exchangelib',
        'cryptography.fernet',
        'openpyxl',
        'vobject',
        'dns.resolver',
        'chardet',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ── Platform-specific icon ────────────────────────────────────────────────
_icon = None
if sys.platform == 'win32' and Path('assets/icon.ico').exists():
    _icon = 'assets/icon.ico'
elif sys.platform == 'darwin' and Path('assets/icon.icns').exists():
    _icon = 'assets/icon.icns'

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EMS_Mail_Fetcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EMS_Mail_Fetcher',
)

# ── macOS .app bundle ─────────────────────────────────────────────────────
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='EMS Mail Fetcher.app',
        icon=_icon,
        bundle_identifier='com.retiredems.mailFetcher',
        info_plist={
            'NSPrincipalClass':          'NSApplication',
            'NSAppleScriptEnabled':      False,
            'CFBundleDisplayName':       'EMS Mail Fetcher',
            'CFBundleVersion':           '1.0.0',
            'CFBundleShortVersionString':'1.0.0',
            'NSHighResolutionCapable':   True,
        },
    )

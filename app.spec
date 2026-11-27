# -*- mode: python ; coding: utf-8 -*-
import os
import re
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo,
    FixedFileInfo,
    StringFileInfo,
    StringTable,
    StringStruct,
    VarFileInfo,
    VarStruct,
)


def _read_app_version():
    """Read APP_VERSION from ps2_utility/updater.py so PE metadata stays in sync."""
    ver = "2.1.1"
    try:
        with open(os.path.join("ps2_utility", "updater.py"), "r", encoding="utf-8") as f:
            m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', f.read(), re.M)
            if m:
                ver = m.group(1).strip()
    except Exception:
        pass
    parts = [int(x) for x in re.findall(r"\d+", ver)[:4]]
    while len(parts) < 4:
        parts.append(0)
    return ver, tuple(parts[:4])


def _locate_tool(name):
    """Locate bundled CLI binary in repo root or tools/ directory."""
    if os.path.exists(name):
        return name
    alt = os.path.join("tools", name)
    if os.path.exists(alt):
        return alt
    return name


APP_VER_STR, APP_VER_TUPLE = _read_app_version()
APP_VER_DOT4 = ".".join(str(x) for x in APP_VER_TUPLE)

win_version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=APP_VER_TUPLE,
        prodvers=APP_VER_TUPLE,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "ZonalRipper (Open Source)"),
                        StringStruct("FileDescription", "PS2 ISO Manager — Open PS2 Loader (OPL) Suite"),
                        StringStruct("FileVersion", APP_VER_DOT4),
                        StringStruct("InternalName", "PS2-ISO-Manager"),
                        StringStruct("LegalCopyright", "Copyright (c) 2026 ZonalRipper. MIT License."),
                        StringStruct("OriginalFilename", "PS2-ISO-Manager.exe"),
                        StringStruct("ProductName", "PS2 ISO Manager"),
                        StringStruct("ProductVersion", APP_VER_STR),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[
        (_locate_tool('bchunk.exe'), '.'),
        (_locate_tool('ziso.exe'), '.'),
        (_locate_tool('chdman.exe'), '.'),
        (_locate_tool('hdl_dump.exe'), '.'),
        (_locate_tool('pfsshell.exe'), '.'),
    ],
    datas=[
        ('templates', 'templates'),
        ('PS2.data.json', '.'),
        ('app_icon.ico', '.')
    ],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto', 'webview.platforms.winforms'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PS2-ISO-Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app_icon.ico'],
    version=win_version_info,
)

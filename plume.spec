# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for Plume, adapted from Scriptorium's approach.
#
# Build (from this folder, on Windows):
#     pip install pyinstaller
#     pyinstaller plume.spec
#
# The result is dist\Plume.exe. On first run the frozen executable writes its
# configuration to %LOCALAPPDATA%\Plume, not the temporary extraction folder.

import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# CustomTkinter ships theme JSON and assets that must be bundled.
ctk_datas = collect_data_files("customtkinter")

# Bundle the icon alongside the executable too (handy for shortcuts).
icon_datas = [
    (os.path.join("icon", "icon-96.ico"), "icon"),
    (os.path.join("icon", "icon-96.png"), "icon"),
]

# Tray support (v1.16) is optional at runtime; only bundle it if it is
# actually installed at freeze time, so building without it still works.
hiddenimports = ["customtkinter"]
try:
    import pystray  # noqa: F401
    import PIL  # noqa: F401

    hiddenimports += ["pystray", "PIL"]
except ImportError:
    pass

a = Analysis(
    ["plume.py"],
    pathex=[],
    binaries=[],
    datas=ctk_datas + icon_datas,
    hiddenimports=hiddenimports,
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
    name="Plume",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                    # windowed app, no console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join("icon", "icon-96.ico"),
)

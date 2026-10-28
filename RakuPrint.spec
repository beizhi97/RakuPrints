# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['app\\main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icon.ico', '.'),
        ('icon.png', '.'),
        ('LICENSE', '.'),
        ('README.zh-CN.md', '.'),
        ('docs/USAGE.zh-CN.md', 'docs'),
    ],
    hiddenimports=[
        'win32print',
        'win32api',
        'win32con',
        'win32gui',
        'pywintypes',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtPrintSupport',
        'fitz',
        'fitz.utils',
        'certifi',
        'certifi_win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

# Qt uses the Windows ICU API. A build host may also have Poppler/Conda's
# incompatible icuuc.dll on PATH; let Windows load its own system DLL.
a.binaries = [
    entry for entry in a.binaries
    if Path(entry[0]).name.lower() not in {'icuuc.dll', 'icuin.dll'}
]

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RakuPrint',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
    version='file_version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='RakuPrint',
)

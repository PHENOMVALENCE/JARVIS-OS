# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
for package in ("winrt", "pywinauto", "whisper_mic", "ollama", "winotify", "pystray"):
    hiddenimports += collect_submodules(package)

analysis = Analysis(
    ["Mark_7.py"],
    pathex=[],
    binaries=[],
    datas=[("GUI_images", "GUI_images"), ("sounds", "sounds"), ("plugins", "plugins"), (".env.example", ".")],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="JARVIS-Mark-7",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

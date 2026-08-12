# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for the J.A.R.V.I.S desktop application.

One-folder rather than one-file: a single executable unpacks to a temporary
directory on every launch, which is the wrong trade for an application that
starts with Windows and holds a resident model.

Several dependencies here load native libraries or read data files at runtime
that PyInstaller cannot see by following imports, so they are collected
explicitly. Getting this wrong produces a build that starts and then fails the
first time somebody speaks, which is why Build-Release.ps1 smoke-tests the
frozen application rather than trusting that it built.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Imported lazily inside functions, so PyInstaller never sees them.
hiddenimports = [
    # Conversation and speech
    "ollama", "openai", "faster_whisper", "ctranslate2",
    "edge_tts", "piper", "pyttsx3", "pygame",
    # Wake word and the runtime it shares with the offline voice
    "openwakeword", "openwakeword.model", "openwakeword.utils", "onnxruntime",
    # Windows integration
    "pywinauto", "winotify", "pystray", "win32com", "win32com.client",
    "winrt.windows.security.credentials.ui",
    "winrt.windows.media.ocr", "winrt.windows.graphics.imaging",
    "winrt.windows.storage", "winrt.windows.storage.streams",
    "winrt.windows.globalization", "winrt.windows.foundation",
    "winrt.windows.foundation.collections",
    # Documents, media, and the rest
    "pypdf", "docx", "pptx", "openpyxl", "icalendar", "send2trash",
    "spotipy", "requests", "numpy", "pycaw", "comtypes",
]

# Native libraries. onnxruntime and ctranslate2 fail at import without theirs,
# and av carries the codecs faster-whisper decodes audio with.
binaries = []
for package in ("onnxruntime", "ctranslate2", "av", "pygame", "piper"):
    try:
        binaries += collect_dynamic_libs(package)
    except Exception:
        pass

# Data read at runtime: wake-word models, phoneme tables, ONNX metadata.
datas = [
    ("GUI_images", "GUI_images"),
    ("sounds", "sounds"),
    ("plugins", "plugins"),
    (".env.example", "."),
]
for package in ("openwakeword", "piper", "onnxruntime", "faster_whisper"):
    try:
        datas += collect_data_files(package)
    except Exception:
        pass

analysis = Analysis(
    ["Mark_7.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # torch is pulled in by whisper_mic but the assistant runs recognition
    # through faster-whisper. Excluding the parts that never load keeps the
    # build from carrying CUDA payloads onto CPU-only machines.
    # torch is 1.19 GB and arrives only through whisper_mic, which faster-whisper
    # replaced. Recognition, the wake word, and the offline voice all run on
    # onnxruntime and ctranslate2 instead, so neither ships.
    excludes=["torch", "torchvision", "torchaudio", "whisper", "whisper_mic",
              "matplotlib", "tkinter.test", "test", "pytest", "IPython", "notebook"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="JARVIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX corrupts some onnxruntime and pygame binaries, and the saving is not
    # worth a build that fails only at runtime.
    upx=False,
    console=False,
    # PyInstaller needs .ico; a .png here silently produces no icon.
    icon="GUI_images/jarvis.ico",
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="JARVIS",
)

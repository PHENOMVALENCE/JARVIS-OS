# Getting started

## Prerequisites

Use a Windows 11 x64 machine with:

- Python 3.11
- PowerShell 5.1 or newer
- A working microphone for voice input
- Ollama for private local conversation and document embeddings
- FFmpeg for the legacy audio stack
- Git and GitHub CLI only when contributing or publishing

The setup script creates an isolated `.venv`; it does not replace other Python installations.

## Source installation

Open PowerShell in the repository directory:

```powershell
.\Setup-Jarvis.ps1
```

The script performs these operations:

1. Creates `.venv` with Python 3.11 if it is missing.
2. Updates pip, setuptools, and wheel.
3. Installs `requirements.txt`.
4. Copies `.env.example` to `.env` when no `.env` exists.
5. Pulls the `nomic-embed-text` Ollama model when Ollama is installed.

The default conversation model is not automatically pulled by this script. Verify or install it with:

```powershell
ollama pull gemma2:2b
ollama list
```

## Launching

Run either launcher:

```powershell
.\Start-Jarvis.ps1
```

or double-click `Start-Jarvis.cmd`.

The launcher:

- verifies that `.venv\Scripts\python.exe` exists;
- adds a discovered FFmpeg directory to `PATH` for the process;
- starts `Mark_7.py` from the repository root.

Only one Mark 7 instance runs at a time. A named Windows mutex causes later launches to exit normally.

## First-run wizard

On first launch, choose whether to enable:

- spoken responses;
- local conversation memory;
- proactive reminders and health alerts;
- Privacy Mode.

The wizard also displays the emergency stop shortcut: `Ctrl+Alt+J`.

## Automatic startup

Enable startup for the current Windows account:

```powershell
.\Install-Startup.ps1
```

This creates the scheduled task `J.A.R.V.I.S Mark 6` for historical compatibility. The task launches the current `Start-Jarvis.ps1`, which starts Mark 7. It uses:

- an at-logon trigger for the current user;
- an interactive, limited-privilege principal;
- hidden PowerShell;
- restart-on-failure settings;
- no execution-time limit.

Disable it with:

```powershell
.\Remove-Startup.ps1
```

The packaged Inno Setup build uses the current user's `Run` registry key when the installer startup option is selected.

## Installation verification

Run:

```powershell
.\.venv\Scripts\python.exe Diagnose-Jarvis.py
```

The diagnostic checks Windows, Python 3.11, entry-point files, Ollama, required runtime modules, and the Ollama service. It returns a nonzero exit code when any check fails.

Also run:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

## Packaged build

Build the folder-based release:

```powershell
.\Build-Release.ps1
```

The executable is written to:

```text
dist\JARVIS-Mark-7\JARVIS-Mark-7.exe
```

The entire `dist\JARVIS-Mark-7` directory is required. Do not copy only the executable.

## What works without cloud credentials

- Local Ollama conversation
- Text entry
- Whisper push-to-talk recognition
- Windows apps, folders, media, clipboard, windows, and volume
- Local notes
- Workflows
- UI Automation
- Local screenshots
- Local document embeddings and search
- Notifications, health checks, audit history, backup, and recovery

Cloud visual analysis and third-party productivity integrations remain unavailable until configured.

# Packaging and distribution

The target is an end user who downloads one file, runs it, and is talking to
J.A.R.V.I.S a few minutes later. They should never see Python, pip, a terminal,
or a clone URL.

```
GitHub Release  ->  JARVIS-Setup-x64.exe  ->  install  ->  launch  ->  wizard  ->  ready
```

This document records the intended architecture and the state of each part.
It is written before the installer pipeline is finished so the decisions are
reviewable rather than implied by a build script.

## Approach

PyInstaller in one-folder mode, wrapped by Inno Setup. Both are already in the
repository (`Build-Release.ps1`, `installer.iss`) and both are proven on this
stack. One-folder rather than one-file: a single executable unpacks to a temp
directory on every launch, which is slow for an application that starts with
Windows and holds a resident model.

Rejected alternatives, and why:

- **MSIX** — would sandbox file and window access, which is most of what the
  assistant does.
- **Embedded CPython plus a launcher** — smaller, but hand-maintaining the
  dependency tree for pywin32, onnxruntime, and PyAudio is a recurring cost.
- **One-file PyInstaller** — unpack cost on every start, and antivirus flags it
  more often.

## What ships, and what does not

| Component | Size | In the installer | Reason |
|---|---|---|---|
| Application code | ~1 MB | Yes | |
| Python runtime and libraries | ~400 MB | Yes | onnxruntime, torch, and PyAudio dominate |
| Speech recognition models | 75–500 MB | **No** | Downloaded on first use, sized to the machine |
| Offline voice | 63 MB | **No** | Downloaded when the offline voice is selected |
| Wake-word model | 3 MB | Yes | Small, and needed before any download can be explained |
| Language model | 1.6–9 GB | **No** | Ollama manages these; the wizard recommends and pulls |

Keeping models out of the installer is the difference between a ~400 MB
download and a multi-gigabyte one, and it lets the wizard pick a model that
suits the machine instead of shipping one choice to everybody.

## Where things live

Nothing that changes at runtime is written inside the installation directory,
so a per-machine install works for a standard user and uninstall leaves nothing
behind.

| Purpose | Location |
|---|---|
| Program files | `%LOCALAPPDATA%\Programs\JARVIS` |
| Settings, database, audit log | `%LOCALAPPDATA%\JARVIS` |
| Logs | `%LOCALAPPDATA%\JARVIS\logs` |
| Downloaded voices | `%LOCALAPPDATA%\JARVIS\models` |
| Speech recognition cache | `%LOCALAPPDATA%\JARVIS\cache` |
| Plugins | `%LOCALAPPDATA%\JARVIS\plugins` |
| Language models | Managed by Ollama in its own location |

`Settings.data_dir` already resolves to `%LOCALAPPDATA%\JARVIS` when frozen, so
the split exists in code today. The audit confirmed no absolute paths are
hard-coded anywhere in `jarvis_os`.

## Installer behaviour

- Per-user install by default, so no administrator prompt.
- Start menu entry always; desktop shortcut optional.
- **Start at sign-in is ticked by default**, because the wake word only works
  while the assistant is running, and a fresh install that cannot answer
  "Hey Jarvis" looks broken.
- Uninstall removes the program, the Run entry, and downloaded models, and
  leaves settings and logs unless the user asks for a clean removal.

## Ollama

Ollama is a separate installation and the wizard cannot silently install it.
The intended flow is to detect it, and if it is missing, explain what it is,
offer to open the download page, and let setup continue so the rest of the
assistant is configured. Deterministic commands, weather, screen reading, and
reminders all work without a language model.

## Outstanding work

1. Point `Build-Release.ps1` at the current dependency set. onnxruntime, piper,
   openwakeword, and the winrt packages were added after it was last touched
   and need explicit PyInstaller hidden imports and binary collection.
2. Move the model download out of first-launch and into the wizard's model
   step, so the size is stated before it is spent.
3. Checksum-verify downloaded models before use.
4. Sign the installer. Unsigned Windows installers trigger SmartScreen, which
   is the single largest obstacle to a non-technical install.
5. Publish the artifact from CI on a tag rather than from a developer machine.

Items 1 and 4 are what stand between the current build and something that can
be handed to somebody else.

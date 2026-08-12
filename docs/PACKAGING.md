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

## Verifying a build

A successful PyInstaller run is not evidence that the bundle works. This
codebase imports heavy dependencies inside functions so startup stays fast, and
PyInstaller follows imports statically, so a build can launch happily and then
fail the first time somebody speaks or reads the screen.

`jarvis_os/selftest.py` imports every lazily-loaded dependency in the order the
running application would, and the executable runs it when `JARVIS_SELFTEST` is
set. Both `Build-Release.ps1` and the release workflow fail the build when it
reports a missing subsystem, so an incomplete bundle never reaches a release.

The order in that list is load-bearing: onnxruntime is imported before the
Windows Runtime, because initialising WinRT first breaks onnxruntime's DLL
load and silently disables the wake word and the offline voice.

## Releasing

`.github/workflows/release.yml` builds from a tag on a clean runner, runs the
test suite, builds the application, runs the frozen self-test, produces the
installer, records SHA-256 checksums, and attaches everything to a draft
release. Publishing stays a human decision.

## Outstanding work

1. **Sign the installer.** Unsigned Windows installers trigger SmartScreen,
   which is the single largest obstacle to a non-technical install. The build
   script already signs when `JARVIS_SIGN_CERTIFICATE` is set; it needs a
   certificate.
2. Move the model download into the wizard's model step so the size is stated
   before it is spent. The model manager supports this; the wizard does not
   call it yet.
3. Checksum-verify downloaded models. Ollama verifies its own; the Piper voice
   and recognition weights are currently taken on trust from their source.
4. Decide whether to ship without `torch`. It is pulled in by `whisper_mic`,
   but recognition runs through faster-whisper, and it is the largest single
   contributor to the bundle.

Item 1 is what stands between the current build and something that can be
handed to somebody else.

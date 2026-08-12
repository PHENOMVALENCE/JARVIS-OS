# J.A.R.V.I.S

[![tests](https://github.com/PHENOMVALENCE/JARVIS-OS/actions/workflows/tests.yml/badge.svg)](https://github.com/PHENOMVALENCE/JARVIS-OS/actions/workflows/tests.yml)
[![release](https://github.com/PHENOMVALENCE/JARVIS-OS/actions/workflows/release.yml/badge.svg)](https://github.com/PHENOMVALENCE/JARVIS-OS/actions/workflows/release.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3119/)
[![platform: Windows 11](https://img.shields.io/badge/platform-Windows%2011-0078d4.svg)](#requirements)
[![local-first](https://img.shields.io/badge/local--first-no%20API%20key%20required-4c1.svg)](#what-runs-where)

**A voice-first operating layer for Windows that runs on your own machine.**

Say *"Hey Jarvis, what's the weather today"* and it answers out loud in about
four seconds. Say *"Jarvis, open Notepad"* and it opens, with a chime instead of
a sentence. It reads your screen, finds your files, controls your windows, sets
reminders, and answers questions from live sources — with the language model,
the speech recognition, and the voice all running locally.

It works in English and Kiswahili.

---

## What runs where

The assistant is usable with no accounts, no API keys, and no internet
connection beyond what individual answers need.

| | Runs locally | Needs the network | Needs a paid key |
|---|---|---|---|
| Wake word, speech recognition, offline voice | ✅ | | |
| Language model (Ollama) | ✅ | | |
| Screen reading (Windows OCR) | ✅ | | |
| File search, window control, reminders | ✅ | | |
| Weather, encyclopedic answers | | ✅ free | |
| Online neural voice | | ✅ free | |
| Current-events search | | | optional |
| Cloud vision, cloud reasoning | | | optional |

Privacy mode blocks screen capture and every cloud path, and is authoritative
over anything that would leave the machine.

## Installing

**For users** — download the installer from
[Releases](https://github.com/PHENOMVALENCE/JARVIS-OS/releases), run it, and the
first launch walks through microphone, voice, wake word, and startup. See
[Getting started](docs/GETTING_STARTED.md).

> The installer is not yet code-signed, so Windows SmartScreen will warn on
> first run. See [Signing](docs/SIGNING.md) for why, and for how to verify a
> download against its published SHA-256 checksum in the meantime.

**For developers** — from a clone:

```powershell
.\Setup-Jarvis.ps1
.\Start-Jarvis.ps1
```

Setup installs dependencies and fetches the language, embedding, wake-word, and
voice models. It needs Python 3.11 and, for the language model,
[Ollama](https://ollama.com).

## Talking to it

```text
Hey Jarvis, what's the weather today
Jarvis, open Notepad and then take a screenshot
close this
what about Berlin
remind me in ten minutes to call mum
read the screen
undo that
run diagnostics
fungua Notepad          (Swahili: open Notepad)
nikumbushe baada ya dakika kumi     (remind me in ten minutes)
```

The full catalogue is in [COMMANDS.md](COMMANDS.md) and the
[User guide](docs/USER_GUIDE.md).

## How it behaves

**It does not narrate what you can see.** Opening an application gets a chime,
not a sentence. Answers, which only exist in what is said, are spoken in full.
Failures are always surfaced, with the reason and the next step.

**It asks before it acts.** Typing into another application, closing one, or
deleting a file all confirm first. Deletion is limited to your own folder, goes
to the Recycle Bin, and `undo that` puts it back. Every action is recorded in a
hash-chained local log.

**It never gets a shell.** The language model cannot run commands. Every
capability is an explicit typed action with declared permissions and a risk
level, and deterministic requests never reach the model at all — the time,
arithmetic, and unit conversions answer in under a millisecond.

**It verifies rather than assumes.** Closing a window sends a close request so
the application can prompt about unsaved work, then confirms the window
actually went. A claim that did not take effect is reported as a failure.

## Speed

Measured on the development machine: Windows 11, CPU only, no GPU.

| | |
|---|---|
| First spoken word of a reply | ~4.4 s |
| First token from a warm model | ~0.9 s |
| Time, maths, conversions, battery | under 1 ms |
| Indexed file search | ~0.27 s |
| Screen OCR | ~0.56 s |
| Spoken weather answer | ~1.6 s |
| Offline speech synthesis (~4 s of audio) | ~0.25 s |

Replies stream, so speech starts while the model is still writing, and the
model is kept resident because loading it costs more than running it.

## Requirements

- Windows 11 (Windows 10 works; the OCR and notification paths are less tested)
- Python 3.11 for a source install
- 8 GB RAM minimum, 16 GB comfortable — setup recommends a model to match
- [Ollama](https://ollama.com) for the language model
- A microphone

## Documentation

| | |
|---|---|
| [Getting started](docs/GETTING_STARTED.md) | Install and first run |
| [User guide](docs/USER_GUIDE.md) | Everything it can do |
| [Commands](COMMANDS.md) | The command catalogue |
| [Configuration](docs/CONFIGURATION.md) | Settings and `.env` |
| [Architecture](docs/ARCHITECTURE.md) | How it is built |
| [Contributing](CONTRIBUTING.md) | Setting up to develop |
| [Plugins](docs/PLUGINS.md) | Extending it |
| [Workflows](docs/WORKFLOWS.md) | Routines and automation |
| [Security model](docs/SECURITY.md) | Permissions, audit, trust boundaries |
| [Packaging](docs/PACKAGING.md) | Building the installer |
| [Signing](docs/SIGNING.md) | Code signing and SmartScreen |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | When something is wrong |
| [Audit](docs/AUDIT.md) | Architecture review and measurements |
| [Changelog](CHANGELOG.md) | What changed |

## Contributing

Contributions are welcome. [CONTRIBUTING.md](CONTRIBUTING.md) covers the
development setup, how to run the tests, and the conventions the codebase
follows — the important ones being that machine-affecting capabilities stay
typed and permission-gated, and that nothing fails silently.

## Licence and credits

MIT. See [LICENSE](LICENSE).

J.A.R.V.I.S began as a fork of
[ColeHacker381/J.A.R.V.I.S](https://github.com/ColeHacker381/J.A.R.V.I.S). The
Mark 5 runtime it came from is still in the repository, and its original
documentation is preserved in [docs/LEGACY.md](docs/LEGACY.md).

Email SMS functionality is provided by AlfredoSequeida's `etext` (c) 2021.

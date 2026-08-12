# Contributing

Thanks for looking. This document covers getting a working development
environment, the conventions the codebase follows, and what a change needs
before it can be merged.

## Getting set up

Windows 11 and Python 3.11. Other Python versions will install but the
dependency set is pinned against 3.11, and several packages have no wheels
elsewhere.

```powershell
git clone https://github.com/PHENOMVALENCE/JARVIS-OS.git
cd JARVIS-OS
.\Setup-Jarvis.ps1        # virtualenv, dependencies, models, diagnostics
.\Start-Jarvis.ps1
```

Setup downloads the language, embedding, wake-word, and voice models. It needs
[Ollama](https://ollama.com) for the language model; everything else works
without it.

Run the tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

They are fast — a few hundred tests in under half a minute — and none of them
need a microphone, a network connection, or a model. Anything that would is
faked, so the suite runs the same on a laptop and on CI.

## How it is put together

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before a first change. The
short version, bottom-up:

```
storage, theme, commands       SQLite, palette, typed contracts
  diagnostics_log              where swallowed failures go
    audio, answers, providers  speech, weather, search, OCR, files
      router                   text -> typed Command
        actions                Command -> effect on the machine
          security             risk policy, confirmation, audit
            assistant          conversation, language, follow-ups
              app              Tk interface, threads, tray, hotkeys
```

## The rules that matter

These are not style preferences. Changes that break them will be asked to
change.

**The language model never gets a shell.** No `shell=True`, no `os.system`, no
`eval`, no `exec`, and no path where model output becomes a command. Every
capability is an explicit typed action.

**Machine-affecting work goes through the permission system.** Add the action
to `capabilities.py` with its risk, permissions, and reversibility. The
permissions screen and the planner read from there, so an action that is not
registered cannot be configured or governed.

**Deterministic beats model-driven.** If a request can be resolved by matching
text, match it in `router.py`. The model is for judgement, not for parsing
"what time is it". A test asserts the router and the registry agree on risk;
it exists because they had already drifted apart once.

**Nothing fails silently.** Catching broadly is fine — it keeps the assistant
alive when a microphone or a network call misbehaves — but log it through
`diagnostics_log.failure()` so it can be found afterwards. A silent failure is
indistinguishable from a feature that was never wired up.

**Verify, do not assume.** An API returning without raising is not evidence
that anything happened. If success can be checked cheaply, add a verifier to
the capability.

**Privacy mode is authoritative.** If a change can capture the screen, read
window titles, or send anything off the machine, it must be suppressed when
privacy mode is on.

**Prefer native and accessible APIs.** Windows APIs, then UI Automation, then
OCR, then a visual model. Clicking at coordinates is a last resort because it
breaks the moment a window moves.

## Adding a capability

Four places, in this order:

1. `capabilities.py` — register it: risk, permissions, reversibility, whether
   it needs the network, and a verifier if success is checkable.
2. `actions.py` — implement the handler and add it to `_handlers`.
3. `router.py` — match the phrasings people actually say, including the ones
   with "Jarvis" and "please" in them (those are stripped for you).
4. `tests/` — cover the happy path, the failure path, and the routing.

The permissions screen picks it up from the registry automatically.

## Tests

Every change needs them. Beyond the happy path, the ones that earn their keep
here are:

- **Failure paths.** What happens with no microphone, no network, no model.
- **Permission behaviour.** That a risky action still confirms.
- **Regression tests for bugs found.** Several exist for bugs that were only
  visible in combination — for example, reading the screen used to disable the
  wake word, because initialising the Windows Runtime before onnxruntime broke
  its DLL load.

Tests must not depend on machine state. If a test needs a window, a device, or
a network, fake it.

## Commits and pull requests

Small, coherent commits. The subject says what changed; the body says why, and
includes the measurement if the change was made for performance.

```
perf: reduce context refresh overhead
feat: add action verification contracts
fix: reading the screen no longer disables the wake word
```

Before opening a pull request: run the full suite, and run the application. A
surprising number of problems in this codebase were only visible by launching
it and looking — two layout bugs and a silent-exit bug were all found that way,
not by tests.

Pull requests should say what the problem was, what changed architecturally,
what a user will notice, what was measured, and what is still not done. Being
explicit about the limitations is more useful than a clean-sounding summary.

## Building a release

```powershell
.\Build-Release.ps1
```

This runs the tests, builds with PyInstaller, and then runs the frozen
application's own self-test, which imports every lazily-loaded dependency
inside the bundle. A successful build is not evidence the bundle works —
PyInstaller follows imports statically, and this codebase imports heavy
dependencies inside functions to keep startup fast. See
[docs/PACKAGING.md](docs/PACKAGING.md).

## Reporting something

Bugs and feature ideas go in
[Issues](https://github.com/PHENOMVALENCE/JARVIS-OS/issues). For a bug, the
output of `run diagnostics` and the tail of `%LOCALAPPDATA%\JARVIS\logs\jarvis.log`
usually identify it immediately.

Security issues go to [SECURITY.md](SECURITY.md) instead, not to a public issue.

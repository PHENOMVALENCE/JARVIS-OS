# Changelog

Notable changes to J.A.R.V.I.S. Measurements are from the development machine:
Windows 11, CPU only, no GPU, 16 GB RAM.

## Unreleased

### Added

- **Context engine.** Windows, clipboard shape, power, and network state behind
  one API, plus the objects a conversation has referred to. "Close this",
  "minimise this", and "open the folder this file is in" resolve
  deterministically rather than being guessed by the model. The assistant's own
  window is never the answer.
- **Capability registry.** Every action declares risk, permissions,
  reversibility, network need, and how success is verified. The permissions
  screen reads from it, so an action cannot exist without being configurable.
  Plugins can register at runtime.
- **Action verification.** Capabilities that can be cheaply checked are checked
  after running; a claim that did not take effect becomes a failure with the
  reason.
- **Response policy.** Visible actions confirm with a tone when spoken to and a
  written line when typed. Answers are still spoken in full. Failures are never
  quiet.
- **Health service.** Sixteen subsystem checks reporting OK, DEGRADED, FAILED,
  DISABLED, or NOT CONFIGURED, each with a remedy. Ask "run diagnostics".
- **Hardware detection and model manager.** Memory, cores, disk, and GPU
  detection; a recommended model profile; installing, switching, and removing
  the language, recognition, and voice models. Download sizes are stated before
  they are spent.
- **Crash recovery.** Clean-shutdown tracking and stale lock detection. After a
  crash, interrupted work is only offered for retry when it is read-only and low
  risk; destructive work is reported, never repeated.
- **Frozen-build self-test.** Imports every lazily-loaded dependency inside the
  packaged executable, so an incomplete bundle fails the build instead of
  failing the first time somebody speaks.
- **Release workflow.** Builds from a tag on a clean runner, runs the tests and
  the frozen self-test, produces the installer, records SHA-256 checksums, and
  attaches them to a draft release.
- Reminders and timers that survive a restart; `Ctrl+Alt+Space` to summon and
  listen; Spotify playback control; Swahili speech, commands, and replies.
- Error logging to a rotating file, reachable through "what went wrong".

### Changed

- **Speech models are no longer reloaded on every request.** They were rebuilt
  per utterance, costing 2.35 s each time (5.81 s against 3.46 s).
- **Settings are read from memory**, not SQLite, in the streaming hot path:
  0.820 ms to 0.0004 ms. They were read once per streamed token.
- **`torch` is no longer bundled.** 1.19 GB, reaching the build only through
  `whisper_mic`, which faster-whisper replaced. There is one recogniser now
  rather than two, and the frozen build is 871 MB.
- The executable is `JARVIS.exe` and installs to `%LOCALAPPDATA%\Programs\JARVIS`.
- "Diagnostics" runs subsystem checks; "what went wrong" reads the failure log.
- Clearing all reminders now confirms first, because there is no undo for it.

### Fixed

- **Reading the screen permanently disabled the wake word.** Initialising the
  Windows Runtime before onnxruntime loads breaks its DLL load, and both the
  wake word and the offline voice run on onnx. One screen read took out
  "Hey Jarvis" for the session, silently, by falling back to a backend with no
  key configured.
- **A release build would have shipped without the wake word, the voices, or
  screen reading.** The packaging spec predated onnxruntime, piper,
  openwakeword, faster-whisper, and the winrt packages.
- **A second launch vanished.** The single-instance guard exited in silence,
  which is indistinguishable from a crash. It now raises the running window.
- Four actions could not be permission-configured, because the permissions
  screen kept its own list that had drifted from the action table.
- The health reporter could fail while reporting a failure.
- The clipboard write had no timeout, unlike every other subprocess call.

## Earlier work

Before the changes above, the assistant gained: spoken-address handling so
"Jarvis, open Notepad" works; neural speech with offline fallback; streaming
replies so speech starts before the model finishes; automatic grounding of
time-sensitive questions in live sources; free weather, indexed file search, and
on-device screen reading; a rebuilt interface with a voice core that reacts to
the microphone; and a guided first-run setup with room calibration.

Two measurements from that period still describe the system: the first spoken
word of a reply arrives in about 4.4 s where it previously took 29 s, and the
first token from a warm model takes 0.9 s where a cold one took 15.4 s.

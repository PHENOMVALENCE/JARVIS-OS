# J.A.R.V.I.S Mark 7 documentation

This handbook describes the Mark 7 desktop assistant as implemented in this repository. It distinguishes current behavior from optional integrations and legacy Mark 5 code.

## Audience map

| If you want to... | Read |
|---|---|
| Install and launch J.A.R.V.I.S | [Getting started](GETTING_STARTED.md) |
| Learn the desktop interface and everyday commands | [User guide](USER_GUIDE.md) |
| Configure models, voice, storage, startup, and permissions | [Configuration reference](CONFIGURATION.md) |
| Build automations | [Workflow guide](WORKFLOWS.md) |
| Enable calendar, email, GitHub, Notion, or Home Assistant | [Integration guide](INTEGRATIONS.md) |
| Add a new capability | [Plugin and action development](PLUGINS.md) |
| Understand the runtime and database | [Architecture and data model](ARCHITECTURE.md) |
| Evaluate safety boundaries | [Security and privacy](SECURITY.md) |
| Back up, diagnose, update, package, or release | [Operations and release guide](OPERATIONS.md) |
| Resolve a failure | [Troubleshooting](TROUBLESHOOTING.md) |
| Run or extend validation | [Testing guide](TESTING.md) |
| Build and ship an installer | [Packaging](PACKAGING.md) |
| Understand the SmartScreen warning | [Code signing](SIGNING.md) |
| Review the architecture and its measurements | [Audit](AUDIT.md) |
| Contribute code | [Contributing](../CONTRIBUTING.md) |
| Report a vulnerability | [Security policy](../SECURITY.md) |
| Read the original project's documentation | [Legacy](LEGACY.md) |

## Version and platform

- Current runtime version: `7.0.0`
- Supported development platform: Windows 11, x64, Python 3.11
- Primary entry point: `Mark_7.py`
- Compatibility entry point: `Mark_6.py` (kept for older shortcuts; it launches Mark 7)
- Legacy reference implementation: `Mark_5.py`
- Local conversational model: Ollama `gemma2:2b` by default; the model manager
  recommends a larger one when the machine can hold it
- Local embedding model: Ollama `nomic-embed-text` by default
- Speech recognition: faster-whisper, `base` for results and `tiny` for live drafts
- Speech output: Piper offline, Edge online, or Windows SAPI, falling back in that order
- Wake word: openWakeWord's pretrained "hey jarvis", local and keyless

Mark 7 is a desktop assistant running on Windows. It is not a replacement kernel or a standalone operating system. "OS" in the project name refers to the integrated assistant experience.

## Core design principles

1. Deterministic local routing handles known computer commands.
2. The language model does not receive a general-purpose shell tool.
3. Every local capability has an explicit action name and risk level.
4. Sensitive actions are confirmed and may require Windows Hello.
5. Plugins declare their actions and cannot bypass `SecureExecutor`.
6. Screen capture, document indexing, memory, wake-word listening, and external integrations are opt-in or configurable.
7. Credentials are stored in Windows Credential Manager, not SQLite or settings exports.
8. Local action attempts are written to a hash-chained audit log.
9. Success is verified where it can be checked cheaply, rather than inferred
   from an API returning without raising.
10. Failures are recorded rather than swallowed, and reachable through
    "what went wrong".
11. Responses are proportionate: work you can see gets a tone, answers get
    spoken, failures are always surfaced.
12. After a crash, interrupted work is only retried when it is read-only.

## Subsystems added since the handbook was first written

| Module | Responsibility |
|---|---|
| `context.py` | What the user is doing now: windows, clipboard shape, power, network, and the objects a conversation referred to. Resolves "this" and "that". |
| `capabilities.py` | The registry describing every action: risk, permissions, reversibility, network need, and how success is verified. |
| `response_policy.py` | How much to say and whether to say it aloud. |
| `health.py` | Sixteen subsystem checks reporting OK, DEGRADED, FAILED, DISABLED, or NOT CONFIGURED, each with a remedy. |
| `hardware.py` | Memory, cores, disk, and GPU detection, and the model profile that suits them. |
| `models.py` | Installing and switching the language, recognition, and voice models. |
| `recovery_state.py` | Clean-shutdown tracking, stale lock detection, and safe crash recovery. |
| `live_transcribe.py` | Voice capture with its own VAD, showing draft text while you speak. |
| `reminders.py` | Timers and reminders that survive a restart. |
| `language.py` | Swahili detection and command translation into the shared routing path. |
| `earcons.py` | Synthesised confirmation tones. |
| `diagnostics_log.py` | Where swallowed failures go. |
| `selftest.py` | Proof that a frozen build can load every subsystem. |
| `settings_cache.py` | In-memory settings reads for the streaming hot path. |

## Documentation conventions

- Paths shown as `data/...` refer to the source checkout runtime.
- Packaged builds store mutable data under `%LOCALAPPDATA%\JARVIS`.
- Commands use PowerShell unless explicitly identified as Python or voice/text commands.
- Features that require credentials are described as optional and fail with a configuration message when credentials are absent.

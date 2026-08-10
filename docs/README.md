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

## Version and platform

- Current runtime version: `7.0.0`
- Supported development platform: Windows 11, x64, Python 3.11
- Primary entry point: `Mark_7.py`
- Compatibility entry point: `Mark_6.py`
- Legacy reference implementation: `Mark_5.py`
- Local conversational model: Ollama `gemma2:2b` by default
- Local embedding model: Ollama `nomic-embed-text` by default

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

## Documentation conventions

- Paths shown as `data/...` refer to the source checkout runtime.
- Packaged builds store mutable data under `%LOCALAPPDATA%\JARVIS`.
- Commands use PowerShell unless explicitly identified as Python or voice/text commands.
- Features that require credentials are described as optional and fail with a configuration message when credentials are absent.

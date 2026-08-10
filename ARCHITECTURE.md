# Mark 7 architecture

Mark 7 adds the following bounded subsystems:

- `storage.py`: idempotent SQLite migrations, typed preferences, and permissions.
- `plugins.py`: manifest validation, enable/disable state, action declarations, and failure isolation.
- `workflows.py`: cancellable execution, conditions, daily/voice triggers, and run history.
- `ui_automation.py`: accessible element discovery and structured control invocation.
- `screen.py`: privacy-gated local capture and optional cloud visual analysis.
- `knowledge.py`: opt-in Office/PDF extraction, Ollama embeddings, incremental indexing, and cited retrieval.
- `proactive.py`: quiet-hours-aware native notifications, daily workflows, and health warnings.
- `credentials.py` and `user_presence.py`: Windows Credential Manager and Windows Hello boundaries.
- `diagnostics.py`, `recovery.py`, and `updates.py`: install verification, safe backup, and release discovery.

No plugin receives a general shell capability. Plugin manifests declare actions and risk, and every plugin action still passes through `SecureExecutor`. The audit log is hash-chained so later modification is detectable.

The desktop runtime is intentionally split into small layers:

- `Mark_7.py` enforces a single instance and starts the app; `Mark_6.py` remains a compatibility launcher.
- `jarvis_os/app.py` owns the Tk desktop UI, tray icon, worker queues, speech output, and confirmations.
- `jarvis_os/router.py` maps common natural language to typed commands without model involvement.
- `jarvis_os/actions.py` contains explicit Windows capabilities. It does not expose a general shell tool.
- `jarvis_os/security.py` applies risk policy and records every local action in SQLite.
- `jarvis_os/assistant.py` handles Ollama/OpenAI conversation, persistent history, and lazy Whisper input.
- `jarvis_os/settings.py` loads non-secret behavior and secrets from the untracked `.env` file.

The UI thread never performs model, microphone, or automation work. Background queues keep the window responsive. Sensitive background actions synchronously request confirmation from the UI thread before continuing.

## Extending actions

Add a typed route in `router.py`, implement a handler in `actions.py`, assign `Risk.MEDIUM` or `Risk.HIGH` when user confirmation is appropriate, and add routing/action tests. Do not route model text into `shell=True`, PowerShell, `cmd.exe`, `eval`, or `exec`.

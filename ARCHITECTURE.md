# Mark 6 architecture

Mark 6 is intentionally split into small layers:

- `Mark_6.py` enforces a single instance and starts the app.
- `jarvis_os/app.py` owns the Tk desktop UI, tray icon, worker queues, speech output, and confirmations.
- `jarvis_os/router.py` maps common natural language to typed commands without model involvement.
- `jarvis_os/actions.py` contains explicit Windows capabilities. It does not expose a general shell tool.
- `jarvis_os/security.py` applies risk policy and records every local action in SQLite.
- `jarvis_os/assistant.py` handles Ollama/OpenAI conversation, persistent history, and lazy Whisper input.
- `jarvis_os/settings.py` loads non-secret behavior and secrets from the untracked `.env` file.

The UI thread never performs model, microphone, or automation work. Background queues keep the window responsive. Sensitive background actions synchronously request confirmation from the UI thread before continuing.

## Extending actions

Add a typed route in `router.py`, implement a handler in `actions.py`, assign `Risk.MEDIUM` or `Risk.HIGH` when user confirmation is appropriate, and add routing/action tests. Do not route model text into `shell=True`, PowerShell, `cmd.exe`, `eval`, or `exec`.

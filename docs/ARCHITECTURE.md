# Architecture and data model

## Runtime flow

```text
Keyboard / microphone / wake word
              |
              v
        AssistantController
              |
     +--------+---------+
     |                  |
workflow phrase    plugin route
     |                  |
     +--------+---------+
              |
       deterministic router
              |
       Command + Risk
              |
       SecureExecutor
              |
 permissions -> confirmation -> optional Hello
              |
      core actions or plugin
              |
      ActionResult + audit
              |
      transcript / speech
```

Unmatched input follows the conversation-provider path instead of the action path.

## Threading

- Tk main thread: widgets, message boxes, window lifecycle.
- `jarvis-actions`: controller and action processing.
- `jarvis-speech`: sequential pyttsx3 output.
- `jarvis-microphone`: each push-to-talk recognition request.
- `jarvis-tray`: pystray event loop.
- `jarvis-proactive`: schedule and system-health checks.
- `jarvis-updates`: one release check at startup.
- `jarvis-wake-word`: Porcupine audio frames when enabled.
- pynput hotkey listener: emergency-stop callback marshaled to Tk.

Sensitive confirmations originating on a worker are scheduled onto Tk and synchronized with a `threading.Event`.

## Main modules

| Module | Responsibility |
|---|---|
| `app.py` | Composition root and desktop UI |
| `assistant.py` | Providers, conversation storage, orchestration, Whisper |
| `commands.py` | Immutable command and result types |
| `router.py` | Deterministic phrase recognition |
| `actions.py` | Explicit Windows capabilities |
| `security.py` | Permissions, confirmation, Hello hook, audit chain |
| `storage.py` | SQLite connection, migrations, settings, permissions |
| `plugins.py` | Discovery, lifecycle, routing, fault isolation |
| `workflows.py` | Definitions, execution, cancellation, history |
| `ui_automation.py` | pywinauto accessible control operations |
| `screen.py` | Capture, masking, optional visual analysis |
| `knowledge.py` | Extraction, chunking, embeddings, retrieval |
| `proactive.py` | Notifications, quiet hours, health checks, schedules |
| `credentials.py` | Windows Credential Manager and redaction |
| `user_presence.py` | Windows Hello and inactivity session |
| `wake_word.py` | Porcupine listener lifecycle |
| `recovery.py` | ZIP backup and safe extraction |
| `diagnostics.py` | Runtime readiness checks |
| `updates.py` | GitHub release discovery |

## Composition order

`JarvisApp` creates dependencies in this order:

1. `Settings` and data directory;
2. `Database` migrations;
3. settings and permission repositories;
4. audit log and security session;
5. knowledge index;
6. core `WindowsActions` and `PluginManager`;
7. `SecureExecutor`;
8. workflow repository and engine;
9. conversation store and provider;
10. assistant controller;
11. proactive scheduler;
12. UI and background services.

## SQLite migrations

`PRAGMA user_version` currently advances through five migrations:

1. settings and permissions;
2. plugins and workflows;
3. workflow runs;
4. indexed documents and chunks;
5. notification history.

Migrations execute only when the stored version is lower than the target and are covered by idempotency tests.

## Tables

### `settings`

`key TEXT PRIMARY KEY`, `value TEXT` containing JSON.

### `permissions`

Action-to-mode mapping with a database check constraint for `allow`, `ask`, and `deny`.

### `plugins`

Plugin ID, enabled flag, and reserved JSON config.

### `workflows`

UUID, name, JSON definition, enabled flag, and timestamps.

### `workflow_runs`

Run ID, workflow ID, timestamps, status, and final message.

### `indexed_documents`

Absolute path, source modification timestamp, and index timestamp.

### `document_chunks`

Source path, optional page/slide/sheet number, text content, and JSON embedding vector.

### `notifications`

Unique event key, timestamp, title, message, and urgency. Event keys suppress duplicates.

### `actions`

Created by `AuditLog`: action attempt fields plus previous and current SHA-256 hashes.

### Conversation database

`conversation.db` contains ordered `role` and `content` rows. It is separate from `jarvis.db`.

## Knowledge pipeline

```text
Configured folders
      |
supported files only
      |
format-specific extraction
      |
1,200-character chunks / 150 overlap
      |
Ollama embeddings
      |
SQLite JSON vectors
      |
cosine similarity
      |
top passages with path/page citations
      |
optional answer synthesis
```

Supported extensions: `.txt`, `.md`, `.pdf`, `.docx`, `.pptx`, `.xlsx`.

Incremental indexing compares exact file modification timestamps. Removed source files are not currently purged automatically; clear or rebuild the index when necessary.

## Packaged layout

The PyInstaller build uses folder mode for fast startup. Code, native libraries, assets, sounds, and plugin sources are under `dist\JARVIS-Mark-7`. Mutable packaged data is redirected to `%LOCALAPPDATA%\JARVIS`.

## Legacy boundary

Mark 5 and `Utilities/` remain for compatibility/reference. Mark 7 does not use the legacy hashtag tool-dispatch loop for its primary action system.

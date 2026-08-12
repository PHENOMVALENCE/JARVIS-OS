# Architecture audit

Taken against `main` at `b0e793a`: 41 modules, 7,113 source lines, 44 typed actions,
240 passing tests. Measurements are from the target machine (Windows 11, CPU only,
no GPU, ~1 GB free of 16 GB).

The system is sound. It has a clear separation between routing, typed actions, and
the permission layer, and the language model is never given a shell. This audit
looks for the places where that structure has eroded, not for reasons to rebuild.

## Dependency map

Layers, from the bottom up. Nothing below depends on anything above it.

```
storage, theme, commands            foundation: SQLite, palette, typed contracts
  diagnostics_log                   failure recording, depended on widely
    audio_level, earcons, speech    audio in and out
    facts, weather, web_research    answer providers
    file_search, music, ocr         capability providers
      router (+ facts)              text -> typed Command
        actions (+ providers)       Command -> effect on the machine
          security                  risk policy, confirmation, audit
            assistant               conversation, language, follow-ups
              app                   Tk UI, threads, tray, hotkeys
```

`app.py` imports 27 modules and is 753 lines. It is the only module that knows
about every other subsystem, which is expected for a UI shell but means it is
also where most cross-cutting state now lives.

## Findings

Ordered by impact. Severity reflects user-visible effect, not code ugliness.

### 1. The speech recogniser is rebuilt on every request — regression

`app._listen_once` constructed a new `LiveTranscriber` for each utterance, so both
faster-whisper models were reloaded from disk every time a person spoke. The
models are cached per instance, and the instance was discarded.

| | |
|---|---|
| Reusing a warm transcriber | 3.46 s |
| Rebuilding it, as shipped | 5.81 s |
| **Wasted per spoken request** | **2.35 s** |

Introduced by the live-transcription change. This directly undoes the warm-model
work done earlier in the same cycle. **Severity: high.**

### 2. Settings are read from SQLite in per-token hot paths

`SettingsRepository.get` opens a SQLite connection per call at **0.77 ms**.
`_render_chunk` runs once per streamed token chunk and calls `_speaks()`, which
reads settings. A 200-chunk reply therefore performs ~200 database opens on the
UI thread, and `_match_voice_to_language` adds another read per reply.

Settings are also read repeatedly during microphone setup (`VoiceConfig.from_settings`
performs ten reads per listen). **Severity: medium** — measurable UI-thread cost
that grows with reply length.

### 3. Actions report success without verifying it

`WindowsActions.execute` treats "the handler returned without raising" as success.
`delete_path` does not confirm the file is gone; `open_app` does not confirm a
process or window appeared; `close_app` trusts `taskkill`'s exit code. Nothing
captures preconditions, success criteria, or rollback data.

This is the single largest gap against the intended
Observe → Understand → Plan → Authorize → Act → **Verify** → Recover → Report model.
**Severity: medium.**

### 4. Context is re-derived ad hoc, per module

There is no shared notion of "what the user is doing now". `actions._matching_window`
enumerates windows for focus and window-state operations; `screen` and `ocr` capture
independently; the assistant tracks `_last_command` and `_last_action_context`
separately from anything the UI knows.

Consequently "close this", "open the folder this file is in", and "what does this
error mean" cannot be resolved. **Severity: medium** — blocks the intended
interaction model rather than breaking anything today.

### 5. Action metadata is spread across three places

Adding an action requires edits in `router.py` (pattern), `actions.py` (handler
dict), and `settings_ui.ACTIONS` (permission list), with risk assigned inline at
each router return. `settings_ui.ACTIONS` has already drifted: `now_playing`,
`add_reminder`, `list_reminders`, and `clear_reminders` are missing from it, so
those actions cannot be permission-configured from the UI. **Severity: medium** —
a live permission inconsistency, not just duplication.

### 6. Responses are uniform regardless of the request

Every result is spoken in full. "Open Notepad" produces a spoken sentence where a
chime would do. There is no policy layer deciding between silence, an earcon, a
short acknowledgement, and a full spoken answer. **Severity: low** but it is the
main thing making the assistant feel like a chatbot rather than an operating layer.

### 7. Smaller items

- **Clipboard write has no timeout.** `copy_clipboard` calls `clip.exe` without one;
  every other subprocess call sets a timeout or uses `CREATE_NO_WINDOW`.
- **Configuration is split** between `Settings` (environment, frozen dataclass) and
  `SettingsRepository.DEFAULTS` (SQLite, 50 keys). Some keys exist in both.
- **Startup work is unconditional.** Update check, model warm, speech warm, and the
  microphone monitor all start regardless of whether they are needed.
- **Four always-on UI timers**: orb 40 ms, chip pulse 90 ms, clock 1 s, plus the
  microphone callback at 50 ms. Individually cheap, collectively the idle cost.
- **No hard-coded absolute paths** were found; `Settings.project_root` and
  `data_dir` are respected throughout, and `models/` is passed in. Good for packaging.
- **No `shell=True`, `os.system`, `eval`, or `exec`** anywhere in `jarvis_os`. The
  "no shell for the model" rule holds.

## What is deliberately not being changed

- The router's regex-first design. It is fast, deterministic, and testable; the
  brief asks for more determinism, not less.
- The Tk interface. It is packaged, themed, and working.
- The plugin and workflow schemas, which are already versioned in SQLite.
- `app.py`'s size. It is a UI shell wiring subsystems together; splitting it would
  be churn without changing behaviour.

## Priorities taken from this audit

1. Fix the transcriber rebuild (finding 1) and the settings hot path (finding 2).
2. Introduce a context engine (finding 4).
3. Add verification contracts to actions (finding 3).
4. Introduce a capability registry and close the permission gap (finding 5).
5. Add a response policy (finding 6).
6. Re-measure and record before/after.

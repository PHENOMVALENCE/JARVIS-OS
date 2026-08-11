# Configuration reference

Mark 7 has three configuration layers:

1. `.env` for provider selection, API keys, and compatibility integrations;
2. SQLite runtime settings managed by the Settings window;
3. Windows Credential Manager for external integration secrets.

Do not commit `.env`, `data/`, OAuth client files, tokens, or packaged runtime databases.

## Environment variables

Copy `.env.example` to `.env` and set only required values.

| Variable | Default | Purpose |
|---|---|---|
| `JARVIS_LLM_PROVIDER` | `ollama` | `ollama` or `openai` conversation provider |
| `OLLAMA_MODEL` | `gemma2:2b` | Compatibility default local conversation model |
| `OPENAI_API_KEY` | empty | OpenAI conversation and screen analysis |
| `OPENAI_ASSISTANT_ID` | empty | Legacy Mark 5 Assistants configuration |
| `OPENAI_THREAD_ID` | empty | Legacy Mark 5 Assistants configuration |
| `PORCUPINE_API_KEY` | empty | Optional wake-word listener |
| `SERPAPI_API_KEY` | empty | Legacy SerpAPI search |
| `ELEVENLABS_API_KEY` | empty | Legacy ElevenLabs support |
| `SPOTIFY_CLIENT_ID` | empty | Spotify Web API client |
| `SPOTIFY_CLIENT_SECRET` | empty | Spotify Web API secret |
| `SPOTIFY_REDIRECT_URI` | `http://localhost:8888/callback` | Spotify OAuth redirect |
| `JARVIS_PHONE_NUMBER` | empty | Legacy SMS bridge |
| `JARVIS_PHONE_PROVIDER` | empty | Legacy SMS carrier |
| `JARVIS_SENDER_EMAIL` | empty | Legacy SMS sender |
| `JARVIS_SENDER_PASSWORD` | empty | Legacy SMS sender password |
| `JARVIS_SPEAK_RESPONSES` | `true` | Initial spoken-response preference |
| `JARVIS_MINIMIZE_TO_TRAY` | `true` | Initial tray preference |
| `JARVIS_WHISPER_MODEL` | `base` | Initial Whisper model |
| `JARVIS_WORK_APPS` | `terminal,spotify` | Compatibility work-mode list |
| `JARVIS_ENABLE_HAND_VOLUME` | `false` | Legacy webcam volume controller |
| `JARVIS_INPUT_MODE` | `voice` | Legacy Mark 5 input mode |

Runtime SQLite preferences override the applicable Ollama model, Whisper model, work apps, speech, tray, memory, privacy, and proactive defaults after the first save.

## Runtime settings

Runtime settings live in the `settings` table as JSON values.

| Key | Default | Meaning |
|---|---:|---|
| `speak_responses` | `true` | Queue text-to-speech after responses |
| `minimize_to_tray` | `true` | Hide instead of exit when closing |
| `startup_enabled` | `false` | UI record of startup preference |
| `privacy_mode` | `false` | Block screenshots and cloud screen analysis |
| `conversation_memory` | `true` | Store and reuse recent conversation |
| `ollama_model` | `gemma2:2b` | Local conversational model |
| `whisper_model` | `base` | Lazy speech-recognition model |
| `hands_free_enabled` | `true` | Begin continuous voice capture shortly after startup |
| `tts_voice` | `david` | Preferred installed Windows voice hint |
| `tts_rate` | `178` | Speech rate, clamped to 100–260 words per minute |
| `tts_volume` | `1.0` | Speech volume, clamped to 0.0–1.0 |
| `work_apps` | `terminal, spotify` | Applications opened by work mode |
| `indexed_folders` | empty | Absolute folders eligible for document indexing |
| `embedding_model` | `nomic-embed-text` | Ollama embedding model |
| `proactive_enabled` | `true` | Scheduler and system alerts |
| `quiet_hours_start` | `22:00` | Beginning of normal-notification suppression |
| `quiet_hours_end` | `07:00` | End of suppression |
| `hello_for_high_risk` | `false` | Verify every high-risk action with Hello |
| `security_timeout_minutes` | `15` | Inactivity before sensitive verification |
| `first_run_complete` | `false` | Setup-wizard completion marker |
| `wake_word_enabled` | `false` | Continuous Porcupine listener |
| `screen_mask_regions` | empty | `[left, top, right, bottom]` rectangles to black out |

Model, microphone, tray-close, security-session, and wake-word changes may require restart because their services are created during application startup or first use.

## Permission modes

The `permissions` table maps action names to `allow`, `ask`, or `deny`. If no row exists:

- low-risk commands default to allow;
- medium- and high-risk commands default to ask.

Changing a plugin's enabled state unloads or reloads its actions. Disabling a plugin prevents routing and execution through that plugin.

## Settings import and export

Settings exports contain only runtime preference keys and typed JSON values. They do not contain:

- `.env` values;
- Windows Credential Manager secrets;
- conversation history;
- audit records;
- indexed document contents or embeddings.

Imports ignore keys not present in `SettingsRepository.DEFAULTS`.

## Source and packaged data paths

Source checkout:

```text
<repository>\data
```

Packaged application:

```text
%LOCALAPPDATA%\JARVIS
```

Bundled assets and plugins are loaded from the PyInstaller resource directory, while mutable data is never stored in the temporary bundle extraction path.

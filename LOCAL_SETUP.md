# J.A.R.V.I.S local setup for PHENOM-PC

## Installed layout

- Project: `C:\Users\PHENOM-PC\Documents\ChatGPT\JARVIS OS\J.A.R.V.I.S`
- Personal GitHub fork: `https://github.com/PHENOMVALENCE/J.A.R.V.I.S`
- `origin`: personal fork
- `upstream`: `https://github.com/ColeHacker381/J.A.R.V.I.S.git`
- Python: 3.11.9 in the project-local `.venv`
- Local LLM runtime: Ollama 0.32.6
- Local model: `gemma2:2b` (about 1.6 GB)
- Audio conversion/playback: FFmpeg 9.0
- Speech recognition: Whisper `base` model, downloaded on first verified import

The original Python 3.13 and 3.14 installations were not changed.

## Start J.A.R.V.I.S

Double-click `Start-Jarvis.cmd`, or run this in PowerShell. Both launch the unified Mark 6 desktop app:

```powershell
Set-Location "C:\Users\PHENOM-PC\Documents\ChatGPT\JARVIS OS\J.A.R.V.I.S"
.\Start-Jarvis.ps1
```

Keyboard and push-to-talk microphone input are available together. Closing the window minimizes it to the notification area by default; use the tray menu to exit fully.

Enable automatic startup with `.\Install-Startup.ps1` and disable it with `.\Remove-Startup.ps1`.

## Private configuration

Real credentials belong only in `.env`. That file is ignored by Git. Never place secrets in `Utilities/constants.py` and never commit `.env`.

The safe default configuration is:

```dotenv
JARVIS_LLM_PROVIDER=ollama
OLLAMA_MODEL=gemma2:2b
JARVIS_ENABLE_HAND_VOLUME=false
JARVIS_INPUT_MODE=voice
JARVIS_SPEAK_RESPONSES=true
JARVIS_MINIMIZE_TO_TRAY=true
JARVIS_WHISPER_MODEL=base
JARVIS_WORK_APPS=terminal,spotify
```

Hand-volume control is disabled initially so the webcam does not start automatically. Set it to `true` only when that behavior is wanted.

### Optional OpenAI mode

Add the following values to `.env`:

```dotenv
JARVIS_LLM_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_ASSISTANT_ID=...
OPENAI_THREAD_ID=...
```

The project uses the OpenAI Assistants API rather than a simple chat-completions call. All three values are required for this legacy mode.

### Optional integrations

- Wake word: `PORCUPINE_API_KEY`
- Google/SerpAPI search: `SERPAPI_API_KEY`
- ElevenLabs: `ELEVENLABS_API_KEY`
- Spotify: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and optionally `SPOTIFY_REDIRECT_URI`
- SMS-by-email: the `JARVIS_PHONE_*` and `JARVIS_SENDER_*` settings
- Gmail/iOS bridge: download OAuth client credentials as `caches and calls\client.json`; its token is written to `caches and calls\token.json`. Both are ignored by Git.

Optional features remain unavailable until their credentials are provided. Local Ollama conversation does not need any API key.

## Rebuild or repair the environment

```powershell
Set-Location "C:\Users\PHENOM-PC\Documents\ChatGPT\JARVIS OS\J.A.R.V.I.S"
.\Setup-Jarvis.ps1
```

Validation commands:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q Mark_5.py GUI.py Utilities
ollama list
```

## Updating from the original repository

First preserve local work on a branch or commit. Then:

```powershell
git fetch upstream
git switch main
git merge --ff-only upstream/main
git push origin main
```

If `--ff-only` refuses, the personal fork and upstream have diverged. Do not force-push; inspect the history and merge or rebase deliberately.

## Installed fixes relative to upstream

- Secrets are loaded from an untracked `.env` file.
- OpenAI resources are contacted only in explicit OpenAI mode.
- The default local model is configurable and set to `gemma2:2b` for this laptop.
- Spotify authentication is lazy and optional.
- Gmail/iOS polling no longer starts during module import.
- A Python 3.11 syntax error in the iOS sender check is fixed.
- Missing MediaPipe and dotenv dependencies are recorded.
- NumPy is pinned to a MediaPipe-compatible version.
- Webcam hand-volume startup is optional and off by default.
- Start and repair scripts are included.

## Known limitations

- Torch reports CPU mode; this machine has Intel Iris Xe graphics rather than an NVIDIA CUDA GPU.
- Local responses will therefore be slower than on a discrete GPU.
- The upstream application has no persistent conversation storage across restarts.
- SMS/Gmail support is experimental and can move matching messages to Gmail Trash.
- Search, Spotify, cloud vision, image generation, and wake-word features require separate accounts and credentials.
- Do not configure automatic Windows startup until interactive use is stable and desired. Camera, microphone, speakers, and third-party services deserve an explicit opt-in.

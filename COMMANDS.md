# J.A.R.V.I.S command guide

## Mark 7 knowledge and productivity

- `Remember submit the application Friday`
- `List notes`
- `Index my documents`
- `Search my documents for the launch budget`
- `Daily brief`
- `Show my calendar`
- `Summarize my email`
- `GitHub summary`
- `Capture project decision to Notion`
- `Home Assistant status`
- `Send email to name@example.com subject Hello message Checking in` — requires high-risk confirmation
- `Install package VideoLAN.VLC` — exact Winget ID, confirmation, and optional Windows Hello
- `Update package VideoLAN.VLC` — exact Winget ID, confirmation, and optional Windows Hello

Indexed folders are opt-in under **Settings → General**. Search results include source paths and PDF/slide/sheet page references. Optional integration secrets are stored with `python Manage-Credentials.py`.

## Structured application automation

- `Read the Notepad window`
- `Click Save in Notepad` — asks first
- `Select second result in Spotify` — asks first
- `Enter hello in Name field in Notepad` — asks first
- `What is on my screen` — asks before capture

Structured control uses Windows accessibility metadata instead of fixed cursor coordinates. Screen analysis is blocked by Privacy Mode.

Commands can be typed or spoken. Wording may vary slightly from these examples.

Optional wake-word listening can be enabled under **Settings → General** after configuring `PORCUPINE_API_KEY`. Saying “Jarvis” then opens the normal push-to-talk listening window.

## Applications, folders, and files

- `Open Spotify`
- `Launch Notepad`
- `Open my Downloads folder`
- `Find the file quarterly report`
- `Close Spotify` — asks for confirmation
- `Delete file Documents\draft.txt` — asks for confirmation and moves it to the Recycle Bin

Applications with known Windows aliases open directly. Other applications are discovered through Start Menu shortcuts. File search is limited to the user's home folder and returns at most 50 results.

## Web, Spotify, media, and sound

- `Search the internet for weather in Dar es Salaam`
- `Research the latest battery technology` — returns an answer with current source URLs
- `Look up the history of quantum computing` — summarizes current web search sources
- `Explain from the web how solar cells work` — provides a source-grounded explanation
- `Play Blinding Lights on Spotify`
- `Pause music`, `Next song`, or `Previous song`
- `Set volume to 40 percent`
- `Volume up` or `Volume down`

## Voice controls

- Hands-free listening is enabled by default. Use **PAUSE LISTENING** or **ENABLE LISTENING** in the Voice Core panel to change it for the current session.
- The microphone button performs one push-to-talk capture even when hands-free mode is paused.
- Recognition pauses while J.A.R.V.I.S speaks so that its own voice is less likely to be transcribed.
- Configure the Whisper model, preferred Windows voice, and speech speed under **Settings → General**.

## Desktop tools

- `Switch to Notepad`
- `Minimize Spotify`
- `Maximize Terminal`
- `Take a screenshot`
- `Read clipboard`
- `Copy meeting at three to the clipboard`
- `Type hello world` — asks for confirmation before typing into the active window
- `Show notification take a break`

Screenshots are stored under `data\screenshots`. Window commands match visible window titles.

## Routines

Set a comma-separated application list in `.env`:

```dotenv
JARVIS_WORK_APPS=terminal,spotify
```

Then say `Start work mode` to open them together.

Mark 7 also provides the **WORKFLOWS** editor for multi-step routines. Workflows support action steps, delays, setting conditions, voice phrases, daily times, cancellation, and failure policies. Each sensitive step retains its normal permission check.

## Conversation

Anything that does not match a local action is sent to the configured conversational model. Recent messages are stored in `data\conversation.db` and restored after a restart. The default provider is Ollama; OpenAI can be selected in `.env`.

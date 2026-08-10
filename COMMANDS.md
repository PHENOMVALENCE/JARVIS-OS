# J.A.R.V.I.S command guide

Commands can be typed or spoken. Wording may vary slightly from these examples.

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
- `Play Blinding Lights on Spotify`
- `Pause music`, `Next song`, or `Previous song`
- `Set volume to 40 percent`
- `Volume up` or `Volume down`

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

## Conversation

Anything that does not match a local action is sent to the configured conversational model. Recent messages are stored in `data\conversation.db` and restored after a restart. The default provider is Ollama; OpenAI can be selected in `.env`.

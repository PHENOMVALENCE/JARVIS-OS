# Troubleshooting

Start with:

```powershell
.\.venv\Scripts\python.exe Diagnose-Jarvis.py
.\.venv\Scripts\python.exe -m pip check
```

## Virtual environment missing

Symptom:

```text
Virtual environment missing. Run .\Setup-Jarvis.ps1 first.
```

Resolution:

```powershell
.\Setup-Jarvis.ps1
```

Confirm Python 3.11 is available through `py -3.11`.

## J.A.R.V.I.S exits immediately

Possible causes:

- another Mark 7 instance owns the singleton mutex;
- a startup exception occurred;
- a packaged folder is incomplete.

Check Task Manager and the tray first. For source debugging, run directly in a visible terminal:

```powershell
.\.venv\Scripts\python.exe Mark_7.py
```

Do not copy only the packaged `.exe`; retain the entire release folder.

## Ollama request fails

Check:

```powershell
ollama list
ollama pull gemma2:2b
ollama pull nomic-embed-text
```

Verify the Ollama background service is running. Model names in Settings must exactly match installed model tags.

## First microphone request is slow

Whisper loads lazily and may download/load model data on first use. Later requests reuse the microphone object. Use a smaller Whisper model on CPU-limited machines.

## Microphone error

- Confirm Windows microphone privacy permission.
- Close applications holding the audio device exclusively.
- Verify PyAudio and the selected default input device.
- Disable wake-word listening while testing push-to-talk.
- Confirm FFmpeg is discoverable for legacy paths.

## Wake word does not start

- Set `PORCUPINE_API_KEY` in `.env`.
- Enable wake word in Settings.
- Restart J.A.R.V.I.S.
- Confirm microphone permission.
- Check that no second instance owns the audio stream.

Missing access keys fail closed and do not start a listener thread.

## Windows Hello unavailable

Installing the WinRT Python package does not configure Hello. In Windows Settings, enroll a PIN, fingerprint, or face credential. The device and current account must report `UserConsentVerifierAvailability.AVAILABLE`.

Leave `hello_for_high_risk` disabled until availability succeeds. When enabled but unavailable, high-risk verification fails closed.

## Application cannot be found

Mark 7 first checks known aliases, then Start Menu `.lnk` files under current-user and all-user program folders. Use the visible Start Menu shortcut name or add a core alias.

## UI Automation cannot find a window/control

- Use a distinctive substring of the visible window title.
- Inspect the window first: `Read the Notepad window`.
- Use the accessible name returned by inspection.
- Ensure the target is visible and not elevated above J.A.R.V.I.S.
- Some custom-rendered controls expose no UI Automation provider.

Mark 7 cannot automate UAC secure-desktop windows.

## Screen analysis says an API key is required

Local capture succeeded, but visual description requires `OPENAI_API_KEY`. The saved screenshot path is returned. Set the key and restart, or use local UI inspection instead.

## Screen capture is blocked

Disable Privacy Mode only when capture is intended. Privacy Mode blocks both screenshot and screen-analysis commands before accessing pixels.

## Document index is empty

1. Add absolute folders in Settings.
2. Verify supported file extensions.
3. Install/pull `nomic-embed-text`.
4. Run `Index my documents` and approve indexing.
5. Review returned extraction errors.

Scanned image-only PDFs may contain no extractable text. OCR is not currently part of document extraction.

## Embedding search fails after changing model

Clear and rebuild the index. Embeddings from different models may have different dimensions and meanings.

## Integration says not configured

Use `Manage-Credentials.py` with the exact credential names in the integration guide. Credentials are stored per Windows account.

## GitHub summary fails

```powershell
gh auth status
gh auth login
```

The current plugin uses GitHub CLI authentication, not the stored `github_token` credential.

## Email fails

- Confirm IMAP/SMTP hostnames.
- Confirm SSL service availability.
- Use an app password when required.
- Check whether SMTP SSL uses port 465 for the provider.
- Remember that OAuth-only providers are not supported by the current plugin.

## Startup task does not run

Inspect:

```powershell
Get-ScheduledTask -TaskName "J.A.R.V.I.S Mark 6"
Get-ScheduledTaskInfo -TaskName "J.A.R.V.I.S Mark 6"
```

Recreate it:

```powershell
.\Remove-Startup.ps1
.\Install-Startup.ps1
```

The GUI requires an interactive signed-in session, so startup is intentionally at logon rather than before login.

## Notification does not appear

- Check `proactive_enabled`.
- Check quiet hours.
- High urgency bypasses quiet hours; normal urgency does not.
- Duplicate event keys appear only once in history.
- Confirm Windows notification settings permit the app.

## Audit integrity warning

Stop sensitive automation and preserve a copy of `jarvis.db`. A warning means one or more hash-chain fields no longer validate. Restoring from a trusted backup may be appropriate. Do not simply delete the warning without understanding the database change.

## Packaged startup is slow

Use the folder-based release. The old one-file layout had to extract hundreds of megabytes at every start. The current installer and CI package the complete folder.

## Build takes a long time

PyInstaller analyzes Torch, Whisper, OpenCV, WinRT, and Office libraries. A clean build can take several minutes and use substantial memory. Avoid launching duplicate builders. The result is excluded from Git by `dist/` and `build/` patterns.

# User guide

## Main window

The desktop window contains:

- **J.A.R.V.I.S** title and current status;
- **WORKFLOWS** button;
- **SETTINGS** button;
- scrollable conversation transcript;
- keyboard input field;
- **MIC** push-to-talk button;
- **SEND** button.

Press Enter in the text field or click **SEND**. Text and microphone input are available in the same session.

Status values include ready, listening, working, no speech, error, and stopped. Model calls, microphone recognition, speech output, workflows, and computer actions run on background threads so the Tk interface remains responsive.

## System tray

When tray behavior is enabled, closing the window hides it instead of exiting. The tray menu can reopen or fully exit J.A.R.V.I.S. If the tray icon cannot initialize, closing exits normally.

## Emergency stop

Press `Ctrl+Alt+J` to:

1. cancel the currently running workflow;
2. clear queued user requests;
3. lock the security session;
4. display a stopped status.

The next sensitive action may require Windows Hello, depending on settings and device availability. Emergency stop cannot forcibly undo an external operation that another application has already completed.

## Voice input

Click **MIC** to start a ten-second listening window. Whisper is loaded lazily on first use, so the first transcription takes longer. If no speech is detected, the status changes without sending an empty request.

Voice configuration:

- `tiny`: fastest, least accurate;
- `base`: default balance;
- `small` or `medium`: higher accuracy and resource usage;
- `large`: highest local requirements.

## Wake word

Wake-word listening is disabled by default. Configure `PORCUPINE_API_KEY` in `.env`, enable wake word in Settings, and restart. Saying "Jarvis" starts the same push-to-talk listening window.

The listener processes microphone frames locally through Porcupine. Disable it when continuous microphone access is not wanted.

## Conversation

Text that does not match a local command is sent to the configured conversational provider. Mark 7 supports:

- Ollama using the configured local model;
- OpenAI chat completions when `JARVIS_LLM_PROVIDER=openai` and `OPENAI_API_KEY` are set.

When memory is enabled, the most recent 20 stored messages are included. Disabling memory prevents new messages from being saved and excludes stored history from requests. Clear existing history under **Settings > Audit history > Clear conversation memory**.

## Permissions

Each action can be configured as:

- `allow`: execute without an application confirmation;
- `ask`: display a confirmation dialog;
- `deny`: block and audit the attempt.

Defaults are allow for ordinary actions and ask for typing, closing, deleting, sending email, installing software, and other declared medium/high-risk operations.

Plugin actions appear in the same permission list.

## Results

Actions return a success flag, message, and optional details. Detailed results appear as bullet lines, including:

- file matches;
- accessible UI controls;
- document citations;
- calendar events;
- unread email headers;
- GitHub notifications;
- Home Assistant entity states.

## Common command groups

See the complete examples in [`COMMANDS.md`](../COMMANDS.md).

### Computer control

```text
Open Spotify
Open my Downloads folder
Find the file quarterly report
Set volume to 40 percent
Switch to Notepad
Maximize Terminal
Read clipboard
```

### Structured UI control

```text
Read the Notepad window
Click Save in Notepad
Select second result in Spotify
```

UI actions search Windows accessibility properties. They are more reliable than fixed mouse coordinates but depend on the target application exposing accessible controls and matching window/control names.

### Knowledge

```text
Index my documents
Search my documents for the launch budget
```

Configure indexed folders first. Indexing and screen capture are permissioned because they read local content.

### Notes and productivity

```text
Remember renew the certificate
List notes
Daily brief
Show my calendar
Summarize my email
GitHub summary
Capture project decision to Notion
Home Assistant status
```

## Screenshots and screen analysis

`Take a screenshot` saves all monitors locally. `What is on my screen` captures the screen and, when an OpenAI key exists, sends the image and prompt for visual analysis.

Privacy Mode blocks capture before the screen is accessed. Configured mask rectangles are painted black before storage or upload.

## File deletion

Deletion:

- is restricted to paths inside the current user's home directory;
- cannot target the home directory itself;
- moves items to the Recycle Bin through `Send2Trash`;
- is high risk and asks by default.

## Package management

Package installation and upgrades accept exact Winget IDs containing only letters, numbers, dots, hyphens, and underscores. They use noninteractive agreement flags, are high risk, and may require Windows Hello.

## Limits

- Mark 7 cannot control secure desktop prompts such as UAC.
- Windows Hello must be configured by Windows before Mark 7 can use it.
- UI Automation cannot read every custom-rendered application.
- Cloud features require network connectivity and valid credentials.
- The assistant does not receive unrestricted shell access.

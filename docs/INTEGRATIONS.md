# Integration guide

Optional integrations are provided by the `productivity` plugin. The plugin is enabled by default but returns configuration messages until credentials exist.

## Managing credentials

Run:

```powershell
.\.venv\Scripts\python.exe Manage-Credentials.py
```

Supported names:

| Credential | Used for |
|---|---|
| `calendar_ics_url` | Calendar ICS URL or local `.ics` path |
| `email_imap_server` | Inbox read server |
| `email_smtp_server` | Optional separate sending server |
| `email_username` | IMAP/SMTP login and From address |
| `email_password` | App password or service credential |
| `github_token` | Reserved; current GitHub action uses authenticated `gh` CLI |
| `notion_token` | Notion integration bearer token |
| `notion_database_id` | Destination database |
| `home_assistant_url` | Base URL such as `http://homeassistant.local:8123` |
| `home_assistant_token` | Long-lived access token |

The helper hides terminal input. Entering a blank value deletes the credential.

## Calendar

`Show my calendar` reads an ICS source and returns events starting within the next 24 hours.

Supported sources:

- HTTPS ICS subscription URL;
- local ICS file path.

Current limitations:

- recurring rules are not expanded beyond explicit components;
- only start time and summary are displayed;
- calendar writes are not implemented.

Treat private ICS URLs as credentials because possession often grants read access.

## Email

`Summarize my email`:

1. opens an SSL IMAP connection;
2. logs in with stored credentials;
3. selects INBOX read-only;
4. finds unread messages;
5. returns up to 20 From/Subject headers.

It does not mark messages as read or download message bodies.

`Send email to ... subject ... message ...` uses SMTP over SSL on port 465. Sending is declared high risk and asks by default.

Use an app-specific password where supported. The current implementation does not provide OAuth flows.

## GitHub

`GitHub summary` runs the authenticated GitHub CLI:

```powershell
gh api notifications --paginate
```

Configure with:

```powershell
gh auth login
gh auth status
```

Up to 30 repository/type/title notification lines are displayed. The action is read-only.

## Notion

`Capture ... to Notion` creates a page in the configured database using the `Name` title property. The text is limited to 1,900 characters.

Requirements:

1. Create a Notion integration.
2. Share the target database with that integration.
3. Store the token and database ID.
4. Ensure the database has a title property named `Name`.

This action is medium risk and asks by default.

## Home Assistant

`Home Assistant status` requests `/api/states` and returns up to 30 entities whose IDs begin with:

- `light.`;
- `lock.`;
- `alarm_control_panel.`.

The current plugin is read-only. Store the base URL without `/api/states` and use a long-lived access token.

## Daily brief

`Daily brief` combines:

1. calendar agenda;
2. unread email summary;
3. GitHub notifications.

The brief succeeds when any component succeeds and includes up to five details from each. Missing integrations contribute an explanatory message rather than aborting other components.

## Spotify

Mark 7 supports launching Spotify searches through the `spotify:` URI without Web API credentials. Legacy playback API functions require:

- `SPOTIFY_CLIENT_ID`;
- `SPOTIFY_CLIENT_SECRET`;
- optional `SPOTIFY_REDIRECT_URI`.

System media keys can pause, resume, skip, and go to the previous track regardless of the active compatible media application.

## OpenAI

Set `OPENAI_API_KEY` for:

- OpenAI conversation when `JARVIS_LLM_PROVIDER=openai`;
- visual screen analysis after permission and Privacy Mode checks.

Screen images are encoded as PNG data URLs and sent to `gpt-4o-mini`. A local screenshot remains in the screenshots directory.

## Wake word

Obtain a Porcupine access key, set `PORCUPINE_API_KEY`, enable wake word, and restart. The built-in keyword is `jarvis`.

## Failure handling

Plugin exceptions become failed `ActionResult` messages and update the plugin's error status. Network calls use timeouts, but a third-party service may still be slow. Repeated failures do not disable a plugin automatically.

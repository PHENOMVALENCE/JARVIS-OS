# Security and privacy

## Threat model

Mark 7 assumes:

- the Windows account owner is trusted;
- natural-language input and model output may be mistaken or adversarial;
- plugin code is privileged local code and must be reviewed before installation;
- third-party services may fail, reject requests, or return untrusted content;
- the desktop process is not a secure sandbox.

Mark 7 is designed to prevent model text from becoming unrestricted shell execution and to preserve user presence for sensitive actions. It does not defend a compromised Windows administrator account or malicious code already running under the same user.

## Action boundary

Known language is converted to an immutable `Command` containing:

- `action`;
- typed `arguments` dictionary;
- `Risk` (`low`, `medium`, or `high`);
- original text.

`SecureExecutor` then:

1. resolves the permission mode;
2. blocks denied actions;
3. asks for confirmation when configured;
4. invokes Windows Hello for approved high-risk actions when required;
5. executes through the core or plugin backend;
6. records the result.

There is no action that accepts arbitrary PowerShell, Command Prompt, Python, `eval`, `exec`, or `shell=True` text from the model.

## Risk examples

Low risk normally includes opening an app, web search, media control, reading configured data, and listing notes.

Medium risk includes:

- typing into another application;
- invoking or selecting accessible UI controls;
- screenshots and screen analysis;
- indexing configured documents;
- closing an application;
- Notion capture.

High risk includes:

- moving files to the Recycle Bin;
- sending email;
- installing or upgrading Winget packages.

Users may override modes, but high-risk actions can still be protected by Windows Hello.

## Windows Hello and session locking

`UserConsentVerifier` is used through the Windows Runtime. Verification fails closed on exceptions or unavailable devices. Windows must report Hello availability; installing the Python package does not enroll the user.

The security session tracks activity with a monotonic clock. It can require verification after inactivity, for every high-risk action, or after emergency lock.

## Emergency stop

`Ctrl+Alt+J` cancels workflow waits, clears pending input work, and locks the security session. It does not terminate unrelated Windows applications or reverse completed network requests.

## Credential storage

`CredentialStore` writes generic credentials with names prefixed by `JARVIS/` to Windows Credential Manager using `win32cred`. Integration secrets are retrieved only when a plugin action needs them.

Use:

```powershell
.\.venv\Scripts\python.exe Manage-Credentials.py
```

Entering an empty value removes the selected credential.

## Audit integrity

The `actions` table records timestamp, action, sorted arguments, risk, approval, success, message, previous hash, and record hash. Each SHA-256 record hash includes the previous record hash.

This detects later modification, deletion, or reordering inside the chain. It does not prevent an attacker with database access from deleting the entire database or constructing a new chain.

The Settings audit tab reports whether verification succeeds.

## Secret redaction

Diagnostic text can be passed through `redact_secrets`, which removes known secret values and common token/password patterns. Developers must not rely solely on pattern matching: never log credential payloads in the first place.

## Privacy controls

- Privacy Mode blocks screen capture before `ImageGrab` is called.
- Screen mask rectangles black out regions before saving or upload.
- Indexed folders are explicit and empty by default.
- Conversation memory can be disabled and cleared.
- Wake-word listening is disabled by default.
- External plugins can be disabled independently.
- Settings exports contain no secrets.
- Deletion is restricted and recoverable.

## Plugin trust

The plugin loader isolates exceptions, validates manifests, and routes declared actions through security. It is not a process sandbox. A malicious Python plugin can still access the user's files and network from its module code. Install only reviewed plugins.

## Network operations

Network traffic may include:

- Ollama calls to the configured local service;
- OpenAI conversation or screen images;
- calendar ICS retrieval;
- IMAP/SMTP email;
- GitHub CLI API requests;
- Notion API requests;
- Home Assistant API requests;
- GitHub release checks;
- Winget downloads.

Privacy Mode currently blocks screen capture/cloud vision; it is not a universal network kill switch.

## Recommended deployment posture

- Run as a standard user, not permanently as administrator.
- Keep high-risk permissions on `ask`.
- Enable Windows Hello only after diagnostics confirm availability.
- Restrict indexed folders to the minimum necessary.
- Use app-specific email passwords or OAuth-capable accounts.
- Review new plugins before enabling them.
- Back up local data and protect the Windows account with disk encryption.

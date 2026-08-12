# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Report it through
[GitHub's private vulnerability reporting](https://github.com/PHENOMVALENCE/JARVIS-OS/security/advisories/new),
which keeps the report private until a fix exists.

Useful things to include: what an attacker can do, how to reproduce it, the
version or commit, and whether it needs local access or can be triggered
remotely — for example through a web page the assistant reads.

This is a personal project maintained by one person, so responses are best
effort rather than guaranteed within a fixed window.

## What is in scope

This assistant runs with the user's own privileges and is designed to control
their machine, so "it can delete a file" is the product working. What matters
is whether it can be made to do something the user did not ask for.

**In scope:**

- Bypassing the permission or confirmation system
- Escaping the typed-action boundary — getting arbitrary commands executed
- Prompt injection that causes an action: content in a web page, a document, a
  screenshot, or a window title that the assistant treats as an instruction
- Reading or leaking secrets: `.env` contents, API keys, Windows Credential
  Manager entries, clipboard contents
- Path traversal or symlink handling that escapes the user's own folder
- Tampering with the audit log without detection
- A plugin gaining capabilities it did not declare
- Privacy mode failing to suppress capture or a cloud call

**Not in scope:**

- The assistant doing what the user asked, including destructive actions that
  were confirmed
- SmartScreen warnings from the unsigned installer — known, documented in
  [docs/SIGNING.md](docs/SIGNING.md)
- Attacks requiring administrator access already obtained by other means
- Vulnerabilities in Ollama, Python, or Windows themselves; report those upstream

## Design boundaries

These are the properties the code is built to hold. A report showing one of
them broken is a valid vulnerability.

**The language model never receives a shell.** There is no `shell=True`, no
`os.system`, no `eval`, and no `exec` anywhere in `jarvis_os`. Every capability
is an explicit typed action with declared permissions.

**Content read from the world is data, never instruction.** Web pages,
documents, OCR text, and window titles are passed to the model as material to
answer from. Nothing in them can authorise an action, because actions are
matched from the user's own words by the router before the model is involved.

**Actions carry risk levels and confirm.** Typing into another application,
closing one, deleting a file, or installing a package all require confirmation.
Deletion is limited to the user's home directory, goes to the Recycle Bin, and
is reversible.

**Everything is recorded.** Each action is written to a hash-chained audit log
in the local SQLite database, so later modification is detectable.

**Privacy mode is authoritative.** It blocks screen capture, suppresses window
titles and clipboard inspection, and disables every cloud path, regardless of
what else is configured.

**Secrets stay out of the database.** Credentials belong in `.env` or Windows
Credential Manager. Settings exports and the SQLite database never contain them.

**Crash recovery never repeats destructive work.** After an unclean shutdown, an
interrupted action is only offered for retry when it is read-only and low risk.

## Keeping an install safe

- Verify downloads against the published `SHA256SUMS.txt`.
- Keep `.env` out of version control — it is already in `.gitignore`.
- Only install plugins you have read. Plugins declare permissions, but a plugin
  is code running in the assistant's process.
- `Ctrl+Alt+J` clears pending work and locks sensitive actions immediately.

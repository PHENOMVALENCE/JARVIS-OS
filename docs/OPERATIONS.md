# Operations and release guide

## Daily operation

Start:

```powershell
.\Start-Jarvis.ps1
```

Exit through the tray menu to stop background listeners and schedulers cleanly. Closing the main window may only hide it.

## Diagnostics

```powershell
.\.venv\Scripts\python.exe Diagnose-Jarvis.py
```

All lines should report `PASS`. The script deliberately prints no credentials or runtime setting values.

## Backup

Use **Settings > Data > Back up local J.A.R.V.I.S data** or call `create_backup` programmatically.

Backups are timestamped ZIP files and include local databases, plugin data, notes, screenshots, and indexes. They exclude SQLite WAL/SHM files and never include Windows Credential Manager secrets or `.env` outside the data directory.

Do not choose a destination inside the data directory. The implementation skips the current output archive, but an external backup location is clearer and safer.

## Restore

Use **Settings > Data > Restore local data backup** and restart afterward. ZIP members are resolved before extraction; any path escaping the destination causes the restore to fail.

For the safest restore:

1. Exit J.A.R.V.I.S from the tray.
2. Copy the current data directory to a separate location.
3. Restore the ZIP.
4. Restart and run diagnostics.

## Audit review

Open **Settings > Audit history**. Verify the integrity label before relying on the records. The view shows the 100 most recent action attempts.

## Document-index maintenance

- Run `Index my documents` after changing configured folders.
- Modified files are reindexed automatically on the next indexing request.
- Clear the index programmatically with `KnowledgeIndex.clear()` when removing folders or changing embedding models.
- Rebuild after switching `embedding_model`; vectors from different models must not be mixed.

## Updates

At startup, `UpdateChecker` queries the latest GitHub release. A newer semantic version creates one local notification per version. Mark 7 does not silently download or execute updates.

Recommended update procedure:

1. Back up data.
2. Review release notes and changed permissions.
3. Pull or install the release.
4. Run setup to update dependencies/models.
5. Run tests and diagnostics.

## Source release build

```powershell
.\Build-Release.ps1
```

This installs `requirements-dev.txt`, runs tests, builds `jarvis.spec`, and optionally signs the executable.

Output:

```text
dist\JARVIS-Mark-7\
  JARVIS-Mark-7.exe
  _internal\...
```

The release directory is large because it includes Torch, Whisper, OpenCV, WinRT, Office parsers, and native dependencies. Folder mode avoids extracting this payload on every startup.

## Code signing

Set these environment variables before building:

```powershell
$env:JARVIS_SIGN_CERTIFICATE = "C:\secure\codesign.pfx"
$env:JARVIS_SIGN_PASSWORD = "..."
.\Build-Release.ps1
```

The script calls `signtool.exe` with SHA-256 and a timestamp server. Never commit the certificate or password.

## Installer

Compile `installer.iss` with Inno Setup after building. It:

- installs the complete folder release under Program Files;
- creates Start Menu and optional desktop shortcuts;
- optionally adds current-user startup;
- supports uninstall.

The installer itself must also be signed for a production release.

## GitHub Actions

`tests.yml` runs on Windows for pushes to main and pull requests:

- Python 3.11 setup;
- dependency installation;
- unit tests;
- compilation.

`release.yml` runs manually or for `v*` tags:

- installs runtime and development dependencies;
- runs tests;
- builds the PyInstaller folder;
- uploads it as a workflow artifact.

The workflow does not currently sign artifacts because certificates are not configured in repository secrets.

## Versioning

Update together:

- `jarvis_os.__version__`;
- Inno Setup `MyAppVersion`;
- documentation version references;
- release tag.

Use semantic versions. Database schema changes must add a new migration rather than rewriting an applied migration.

## Release checklist

- [ ] Full test suite passes.
- [ ] `pip check` passes.
- [ ] Python and PowerShell compilation/parsing pass.
- [ ] Diagnostics pass on a clean Windows account.
- [ ] Text, microphone, tray, and Ollama conversation are smoke-tested.
- [ ] UI Automation is tested against a real application.
- [ ] Screen privacy checks occur before capture.
- [ ] Document embedding and cited search are tested.
- [ ] High-risk confirmations and emergency stop are tested.
- [ ] Folder release launches within an acceptable window.
- [ ] Packaged data is written to `%LOCALAPPDATA%\JARVIS`.
- [ ] Installer install, startup, update, and uninstall are tested.
- [ ] Executable and installer signatures verify.
- [ ] Release notes identify migrations and permission changes.

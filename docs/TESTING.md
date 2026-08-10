# Testing guide

## Run all tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The current suite covers command routing, action safety, conversation memory, credentials, semantic indexing, plugins, proactive notifications, recovery, privacy, audit integrity, settings migrations, updates, Windows Hello session behavior, wake-word failure behavior, and workflows.

## Static validation

```powershell
.\.venv\Scripts\python.exe -m compileall -q Mark_7.py Mark_6.py jarvis_os plugins
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Parse PowerShell scripts without executing them:

```powershell
$scripts = @(
  "Setup-Jarvis.ps1",
  "Start-Jarvis.ps1",
  "Install-Startup.ps1",
  "Remove-Startup.ps1",
  "Build-Release.ps1"
)

foreach ($script in $scripts) {
  $errors = $null
  [void][System.Management.Automation.Language.Parser]::ParseFile(
    (Resolve-Path $script), [ref]$null, [ref]$errors
  )
  if ($errors) { throw "$script has parse errors" }
}
```

## Test design

- Use temporary directories for databases and user files.
- Close SQLite connections deterministically so Windows can remove temporary files.
- Mock external actions, network services, Hello verification, and notifications.
- Assert that blocked operations do not call the underlying executor.
- Test risk levels as part of routing behavior.
- Test privacy checks before importing/calling capture libraries.
- Test archive path traversal.
- Keep runtime-generated GUI images out of commits.

## Manual smoke tests

### Source launch

Start `Mark_7.py`, wait for the window, enter a harmless local command, and exit through the tray.

### Ollama

Ask a simple conversation question and verify a local response. Generate one embedding and confirm a nonempty vector.

### Voice

Press MIC, speak a short phrase, and verify transcription and action routing. Repeat to confirm the lazy model is reused.

### UI Automation

Open Notepad and run `Read the Notepad window`. Verify accessible control names. Test a medium-risk control only after reviewing confirmation text.

### Screen privacy

Enable Privacy Mode and verify screenshot and screen-analysis commands fail without creating a new image.

### Knowledge

Index a temporary folder containing a unique sentence, search for it, and verify the source citation.

### Security

- Deny an action and verify no backend call.
- Ask and cancel.
- Press `Ctrl+Alt+J` during a workflow delay.
- Verify audit integrity.
- Test Windows Hello only on an enrolled machine.

### Packaged build

Launch `dist\JARVIS-Mark-7\JARVIS-Mark-7.exe` while retaining `_internal`. Verify it stays alive, creates `%LOCALAPPDATA%\JARVIS\jarvis.db`, and starts substantially faster than the deprecated one-file build.

## Adding tests

Name files `tests/test_<subsystem>.py` and use standard-library `unittest`. New features should test:

1. successful behavior;
2. invalid input;
3. missing configuration;
4. permission/risk behavior;
5. cleanup and Windows path semantics;
6. external failure.

## CI differences

GitHub Actions runs on a clean Windows image and may not have Ollama models, audio hardware, Windows Hello enrollment, or third-party credentials. Unit tests must mock those boundaries. Live integration and hardware checks remain documented manual release tests.

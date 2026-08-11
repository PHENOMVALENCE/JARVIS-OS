"""Enable or disable launching J.A.R.V.I.S when the user signs in.

A scheduled task is used rather than a Run key because it survives crashes,
runs only in the interactive session, and holds limited privileges. When the
app is running as a frozen executable there is no PowerShell script beside it,
so fall back to the per-user Run key.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


TASK_NAME = "J.A.R.V.I.S"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "JARVIS"


def _run_script(script: Path) -> tuple[bool, str]:
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if completed.returncode:
        return False, (completed.stderr or completed.stdout).strip() or "The startup task could not be updated."
    return True, "Startup updated."


def _set_run_key(enabled: bool) -> tuple[bool, str]:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, f'"{sys.executable}"')
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
    except OSError as exc:
        return False, str(exc)
    return True, "Startup updated."


def set_startup(enabled: bool, project_root: Path | None = None) -> tuple[bool, str]:
    """Turn sign-in startup on or off. Returns (succeeded, message)."""
    if getattr(sys, "frozen", False):
        return _set_run_key(enabled)
    root = Path(project_root or Path(__file__).resolve().parent.parent)
    script = root / ("Install-Startup.ps1" if enabled else "Remove-Startup.ps1")
    if not script.exists():
        return _set_run_key(enabled)
    return _run_script(script)


def is_enabled() -> bool:
    """Best-effort check of whether startup is currently configured."""
    completed = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", TASK_NAME],
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if completed.returncode == 0:
        return True
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
        return True
    except (OSError, FileNotFoundError):
        return False

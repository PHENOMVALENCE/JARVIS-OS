"""Installation and runtime diagnostics without exposing credentials."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Diagnostic:
    name: str
    success: bool
    detail: str


def run_diagnostics(project_root: Path) -> list[Diagnostic]:
    results = [
        Diagnostic("Windows", platform.system() == "Windows", platform.platform()),
        Diagnostic("Python", sys.version_info[:2] == (3, 11), platform.python_version()),
        Diagnostic("Project files", (project_root / "Mark_6.py").is_file(), str(project_root)),
        Diagnostic("Ollama executable", shutil.which("ollama") is not None, shutil.which("ollama") or "not found"),
    ]
    for module in ("tkinter", "ollama", "whisper_mic", "pywinauto", "winotify", "winrt.windows.security.credentials.ui"):
        results.append(Diagnostic(f"Module {module}", importlib.util.find_spec(module) is not None, "available" if importlib.util.find_spec(module) else "missing"))
    try:
        completed = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=15)
        results.append(Diagnostic("Ollama service", completed.returncode == 0, completed.stdout.splitlines()[1] if len(completed.stdout.splitlines()) > 1 else completed.stderr.strip()))
    except Exception as exc:
        results.append(Diagnostic("Ollama service", False, str(exc)))
    return results

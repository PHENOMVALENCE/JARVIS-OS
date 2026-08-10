"""Environment-backed settings for the Mark 6 desktop runtime."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DEFAULT_DATA_DIR = (
    Path(os.environ.get("LOCALAPPDATA", Path.home())) / "JARVIS"
    if getattr(sys, "frozen", False)
    else PROJECT_ROOT / "data"
)
load_dotenv(PROJECT_ROOT / ".env")


def env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    data_dir: Path = DEFAULT_DATA_DIR
    llm_provider: str = os.getenv("JARVIS_LLM_PROVIDER", "ollama").lower()
    ollama_model: str = os.getenv("OLLAMA_MODEL", "gemma2:2b")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    speak_responses: bool = env_bool("JARVIS_SPEAK_RESPONSES", True)
    minimize_to_tray: bool = env_bool("JARVIS_MINIMIZE_TO_TRAY", True)
    whisper_model: str = os.getenv("JARVIS_WHISPER_MODEL", "base")

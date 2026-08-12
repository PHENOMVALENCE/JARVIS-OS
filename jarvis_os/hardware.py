"""What this machine can actually run.

The assistant is installed on whatever the user has, and the difference between
a 32 GB workstation and a 8 GB laptop decides which model is sensible. Guessing
produces either a model that swaps to disk or one far weaker than the machine
deserves.

Everything here is read through standard libraries and Windows APIs, so it
works before any optional dependency is installed and before a model is chosen.
"""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from .diagnostics_log import failure

GIGABYTE = 1024 ** 3


@dataclass(frozen=True)
class Hardware:
    system: str
    release: str
    architecture: str
    processor: str
    cores: int
    total_ram_gb: float
    available_ram_gb: float
    free_disk_gb: float
    gpu: str = ""
    vram_gb: float = 0.0

    @property
    def has_gpu(self) -> bool:
        return bool(self.gpu)

    @property
    def is_supported(self) -> bool:
        return self.system == "Windows"


@dataclass(frozen=True)
class ModelProfile:
    """A recommended configuration for a class of machine."""

    name: str
    model: str
    download_gb: float
    needs_ram_gb: float
    speech_model: str
    summary: str


# Sizes are the published download sizes, rounded up. The RAM figure is what the
# model needs resident, not the machine total.
PROFILES: tuple[ModelProfile, ...] = (
    ModelProfile(
        "Lightweight", "gemma2:2b", 1.6, 3.0, "tiny",
        "For machines with little memory to spare. Conversational, quick, and modest at reasoning.",
    ),
    ModelProfile(
        "Standard", "llama3.1:8b", 4.7, 6.0, "base",
        "For a typical 16 GB machine. Noticeably better reasoning and much better in languages other than English.",
    ),
    ModelProfile(
        "Performance", "qwen2.5:14b", 9.0, 11.0, "small",
        "For 32 GB machines or a discrete GPU. Strong reasoning and coding.",
    ),
)


def _memory() -> tuple[float, float]:
    """Total and available physical memory, in gigabytes."""
    class Status(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = Status()
    status.dwLength = ctypes.sizeof(Status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return 0.0, 0.0
    return status.ullTotalPhys / GIGABYTE, status.ullAvailPhys / GIGABYTE


def _gpu() -> tuple[str, float]:
    """Discrete GPU name and memory, if one is present and reports itself."""
    try:
        import subprocess

        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode == 0 and completed.stdout.strip():
            name, memory = completed.stdout.strip().splitlines()[0].split(",")
            return name.strip(), float(memory.strip()) / 1024
    except (FileNotFoundError, OSError):
        # No nvidia-smi means no NVIDIA GPU, which is ordinary rather than a fault.
        pass
    except Exception as error:
        failure("hardware.gpu", error)
    return "", 0.0


def detect(path: Path | None = None) -> Hardware:
    """Inspect the machine. Never raises; unknown values come back as zero."""
    total, available = 0.0, 0.0
    try:
        total, available = _memory()
    except Exception as error:
        failure("hardware.memory", error)
    free_disk = 0.0
    try:
        target = path or Path(os.environ.get("SYSTEMDRIVE", "C:") + "\\")
        free_disk = shutil.disk_usage(str(target)).free / GIGABYTE
    except Exception as error:
        failure("hardware.disk", error)
    gpu, vram = _gpu()
    return Hardware(
        system=platform.system(),
        release=platform.release(),
        architecture=platform.machine(),
        processor=platform.processor() or "unknown",
        cores=os.cpu_count() or 1,
        total_ram_gb=round(total, 1),
        available_ram_gb=round(available, 1),
        free_disk_gb=round(free_disk, 1),
        gpu=gpu,
        vram_gb=round(vram, 1),
    )


def recommend(hardware: Hardware) -> ModelProfile:
    """Pick the largest profile the machine can hold without swapping.

    Total memory decides the ceiling rather than free memory, because free
    memory moves with whatever is open; a browser closing should not change
    which model the assistant is configured to use.
    """
    if hardware.has_gpu and hardware.vram_gb >= 10:
        return PROFILES[2]
    if hardware.total_ram_gb >= 30:
        return PROFILES[2]
    if hardware.total_ram_gb >= 15:
        return PROFILES[1]
    return PROFILES[0]


def fits(profile: ModelProfile, hardware: Hardware) -> tuple[bool, str]:
    """Whether a profile can be installed and run right now."""
    if hardware.free_disk_gb and hardware.free_disk_gb < profile.download_gb + 2:
        return False, (f"{profile.name} needs about {profile.download_gb:.1f} GB to download "
                       f"and only {hardware.free_disk_gb:.1f} GB is free.")
    if hardware.total_ram_gb and hardware.total_ram_gb < profile.needs_ram_gb + 2:
        return False, (f"{profile.name} needs about {profile.needs_ram_gb:.0f} GB of memory "
                       f"and this machine has {hardware.total_ram_gb:.0f} GB.")
    return True, ""


def pressure_warning(hardware: Hardware, profile: ModelProfile) -> str:
    """Say when the machine will run the model but is currently too busy."""
    if not hardware.available_ram_gb or not hardware.total_ram_gb:
        return ""
    if hardware.available_ram_gb < profile.needs_ram_gb:
        return (f"Only {hardware.available_ram_gb:.1f} GB of {hardware.total_ram_gb:.0f} GB is free "
                f"right now, and {profile.name.lower()} wants about {profile.needs_ram_gb:.0f} GB. "
                "It will run, but closing some windows will make it noticeably faster.")
    return ""


def summary(hardware: Hardware) -> str:
    parts = [
        f"{hardware.system} {hardware.release} ({hardware.architecture})",
        f"{hardware.cores} cores",
        f"{hardware.total_ram_gb:.0f} GB RAM ({hardware.available_ram_gb:.1f} GB free)",
        f"{hardware.free_disk_gb:.0f} GB disk free",
    ]
    parts.append(f"{hardware.gpu} with {hardware.vram_gb:.0f} GB" if hardware.has_gpu else "no discrete GPU")
    return " · ".join(parts)

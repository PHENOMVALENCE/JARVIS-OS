"""Safe local-data backup and restore."""

from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path


def create_backup(data_dir: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"jarvis-backup-{datetime.now():%Y%m%d-%H%M%S}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        if data_dir.is_dir():
            for path in data_dir.rglob("*"):
                if path.is_file() and path.suffix not in {".db-wal", ".db-shm"}:
                    bundle.write(path, path.relative_to(data_dir))
    return archive


def restore_backup(archive: Path, data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (data_dir / member.filename).resolve()
            if data_dir.resolve() not in target.parents and target != data_dir.resolve():
                raise ValueError("Backup contains an unsafe path.")
        bundle.extractall(data_dir)

"""File lookup through the Windows Search index.

Walking the whole home folder took long enough that "find my budget" felt
broken. Windows already maintains an index of these files, so ask it instead
and keep the directory walk only as a fallback for unindexed locations.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path


SKIPPED_DIRECTORIES = {".git", ".venv", "node_modules", "AppData", "__pycache__"}


def _escape(value: str) -> str:
    """Single quotes terminate a literal in Windows Search SQL."""
    return value.replace("'", "''")


class FileSearch:
    def __init__(self, home: Path | None = None, limit: int = 50):
        self.home = home or Path.home()
        self.limit = limit

    def search(self, query: str) -> list[str]:
        query = query.strip().strip("*? ")
        if not query:
            return []
        indexed = self._from_index(query)
        return indexed if indexed else self._from_walk(query)

    def _from_index(self, query: str) -> list[str]:
        """Ask the Windows Search index. Returns [] when it is unavailable."""
        try:
            import win32com.client
        except ImportError:
            return []
        connection = None
        try:
            connection = win32com.client.Dispatch("ADODB.Connection")
            connection.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
            statement = (
                f"SELECT TOP {int(self.limit)} System.ItemPathDisplay FROM SYSTEMINDEX "
                f"WHERE System.FileName LIKE '%{_escape(query)}%' "
                f"AND SCOPE = 'file:{_escape(str(self.home))}'"
            )
            records = connection.Execute(statement)[0]
            return list(self._drain(records))
        except Exception:
            return []
        finally:
            if connection is not None:
                try:
                    connection.Close()
                except Exception:
                    pass

    def _drain(self, records) -> Iterable[str]:
        count = 0
        while not records.EOF and count < self.limit:
            value = records.Fields.Item(0).Value
            if value:
                yield str(value)
                count += 1
            records.MoveNext()

    def _from_walk(self, query: str) -> list[str]:
        """Fallback for locations Windows has not indexed."""
        needle = query.lower()
        matches: list[str] = []
        for root, directories, files in os.walk(self.home):
            directories[:] = [d for d in directories if d not in SKIPPED_DIRECTORIES]
            for name in (*directories, *files):
                if needle in name.lower():
                    matches.append(str(Path(root) / name))
                    if len(matches) >= self.limit:
                        return matches
        return matches

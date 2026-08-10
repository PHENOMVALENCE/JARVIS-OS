"""Non-destructive release discovery for signed J.A.R.V.I.S updates."""

from __future__ import annotations

import re

import requests


class UpdateChecker:
    API = "https://api.github.com/repos/PHENOMVALENCE/J.A.R.V.I.S/releases/latest"

    def check(self, current_version: str) -> dict | None:
        response = requests.get(self.API, timeout=10, headers={"Accept": "application/vnd.github+json"})
        if response.status_code == 404:
            return None
        response.raise_for_status()
        release = response.json()
        latest = str(release.get("tag_name", "")).lstrip("v")
        if self._version(latest) > self._version(current_version):
            return {"version": latest, "url": release.get("html_url", ""), "name": release.get("name", latest)}
        return None

    @staticmethod
    def _version(value: str) -> tuple[int, ...]:
        parts = re.findall(r"\d+", value)
        return tuple(int(part) for part in parts[:3]) or (0,)

"""Spotify playback control.

The assistant could only open a Spotify search URL, which leaves you clicking.
With credentials configured it can actually start a track, skip, and say what
is playing. Without them it still falls back to opening Spotify, so the
feature degrades rather than disappearing.

Scopes are the minimum needed to control playback and read the current track.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .diagnostics_log import failure

SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing"


@dataclass(frozen=True)
class Track:
    title: str
    artist: str

    def __str__(self) -> str:
        return f"{self.title} by {self.artist}" if self.artist else self.title


class SpotifyControl:
    """Thin wrapper over spotipy that never raises at the call site."""

    def __init__(self, cache_path=None):
        self.cache_path = cache_path
        self._client = None

    @property
    def configured(self) -> bool:
        return bool(
            os.getenv("SPOTIFY_CLIENT_ID", "").strip()
            and os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
        )

    def client(self):
        """Authenticate lazily; the first call may open a browser once."""
        if self._client is not None:
            return self._client
        if not self.configured:
            return None
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        self._client = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.getenv("SPOTIFY_CLIENT_ID", "").strip(),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", "").strip(),
            redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback").strip(),
            scope=SCOPES,
            cache_path=str(self.cache_path) if self.cache_path else None,
            open_browser=True,
        ))
        return self._client

    # ------------------------------------------------------------ actions

    def _device(self, client) -> str | None:
        """Prefer an already-active device, else any available one."""
        devices = (client.devices() or {}).get("devices") or []
        if not devices:
            return None
        active = next((d for d in devices if d.get("is_active")), devices[0])
        return active.get("id")

    def play_query(self, query: str) -> tuple[bool, str]:
        client = self.client()
        if client is None:
            return False, ""
        try:
            results = client.search(q=query, type="track", limit=1)
            items = ((results or {}).get("tracks") or {}).get("items") or []
            if not items:
                return False, f"I could not find {query} on Spotify."
            track = items[0]
            device = self._device(client)
            if device is None:
                return False, "No Spotify device is available. Open Spotify and try again."
            client.start_playback(device_id=device, uris=[track["uri"]])
            name = Track(track["name"], track["artists"][0]["name"] if track.get("artists") else "")
            return True, f"Playing {name}."
        except Exception as error:
            failure("spotify.play", error)
            return False, ""

    def control(self, operation: str) -> tuple[bool, str]:
        client = self.client()
        if client is None:
            return False, ""
        try:
            device = self._device(client)
            if operation == "pause":
                client.pause_playback(device_id=device)
                return True, "Paused."
            if operation == "play":
                client.start_playback(device_id=device)
                return True, "Resumed."
            if operation == "next":
                client.next_track(device_id=device)
                return True, "Skipped."
            if operation == "previous":
                client.previous_track(device_id=device)
                return True, "Back a track."
            return False, ""
        except Exception as error:
            failure("spotify.control", error)
            return False, ""

    def now_playing(self) -> tuple[bool, str]:
        client = self.client()
        if client is None:
            return False, ""
        try:
            current = client.current_user_playing_track()
            if not current or not current.get("item"):
                return True, "Nothing is playing."
            item = current["item"]
            track = Track(item["name"], item["artists"][0]["name"] if item.get("artists") else "")
            return True, f"{track}."
        except Exception as error:
            failure("spotify.now_playing", error)
            return False, ""

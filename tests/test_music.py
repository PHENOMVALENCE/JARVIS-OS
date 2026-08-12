import unittest
from unittest.mock import Mock, patch

from jarvis_os.actions import WindowsActions
from jarvis_os.music import SpotifyControl, Track
from jarvis_os.router import CommandRouter


def _client(devices=None, search=None, current=None):
    client = Mock()
    client.devices.return_value = {"devices": devices if devices is not None else [{"id": "abc", "is_active": True}]}
    client.search.return_value = search
    client.current_user_playing_track.return_value = current
    return client


class SpotifyControlTests(unittest.TestCase):
    def setUp(self):
        self.control = SpotifyControl()

    def test_unconfigured_returns_no_message_so_callers_can_fall_back(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(self.control.play_query("anything"), (False, ""))
            self.assertEqual(self.control.control("pause"), (False, ""))

    def test_plays_the_first_search_result(self):
        client = _client(search={"tracks": {"items": [
            {"uri": "spotify:track:1", "name": "Bohemian Rhapsody", "artists": [{"name": "Queen"}]}
        ]}})
        self.control.client = lambda: client
        succeeded, message = self.control.play_query("bohemian rhapsody")
        self.assertTrue(succeeded)
        self.assertIn("Bohemian Rhapsody by Queen", message)
        client.start_playback.assert_called_once()

    def test_says_so_when_nothing_matches(self):
        self.control.client = lambda: _client(search={"tracks": {"items": []}})
        succeeded, message = self.control.play_query("asdfgh")
        self.assertFalse(succeeded)
        self.assertIn("could not find", message)

    def test_explains_when_no_device_is_available(self):
        client = _client(devices=[], search={"tracks": {"items": [
            {"uri": "u", "name": "Song", "artists": [{"name": "Artist"}]}
        ]}})
        self.control.client = lambda: client
        succeeded, message = self.control.play_query("song")
        self.assertFalse(succeeded)
        self.assertIn("No Spotify device", message)

    def test_transport_controls_map_to_the_api(self):
        client = _client()
        self.control.client = lambda: client
        self.assertTrue(self.control.control("pause")[0])
        client.pause_playback.assert_called_once()
        self.assertTrue(self.control.control("next")[0])
        client.next_track.assert_called_once()

    def test_reports_the_current_track(self):
        self.control.client = lambda: _client(current={
            "item": {"name": "Hey Jude", "artists": [{"name": "The Beatles"}]}
        })
        succeeded, message = self.control.now_playing()
        self.assertTrue(succeeded)
        self.assertIn("Hey Jude by The Beatles", message)

    def test_reports_silence_clearly(self):
        self.control.client = lambda: _client(current=None)
        self.assertEqual(self.control.now_playing(), (True, "Nothing is playing."))

    def test_an_api_failure_falls_back_rather_than_raising(self):
        client = _client()
        client.search.side_effect = OSError("network down")
        self.control.client = lambda: client
        self.assertEqual(self.control.play_query("song"), (False, ""))

    def test_track_formats_without_an_artist(self):
        self.assertEqual(str(Track("Untitled", "")), "Untitled")


class ActionFallbackTests(unittest.TestCase):
    def test_playing_falls_back_to_opening_spotify(self):
        actions = WindowsActions()
        actions.music.play_query = lambda _q: (False, "")
        with patch("jarvis_os.actions.os.startfile") as startfile:
            result = actions.spotify_play({"query": "jazz"})
        self.assertTrue(result.success)
        startfile.assert_called_once()

    def test_media_falls_back_to_the_media_keys(self):
        actions = WindowsActions()
        actions.music.control = lambda _op: (False, "")
        with patch("jarvis_os.actions.ctypes") as fake_ctypes:
            result = actions.media({"operation": "pause"})
        self.assertTrue(result.success)
        self.assertTrue(fake_ctypes.windll.user32.keybd_event.called)

    def test_media_prefers_spotify_when_available(self):
        actions = WindowsActions()
        actions.music.control = lambda _op: (True, "Paused.")
        self.assertEqual(actions.media({"operation": "pause"}).message, "Paused.")


class RoutingTests(unittest.TestCase):
    def test_routes_now_playing_questions(self):
        router = CommandRouter()
        for text in ("What is playing", "What song is this", "Name of this song"):
            self.assertEqual(router.route(text).action, "now_playing", text)


if __name__ == "__main__":
    unittest.main()

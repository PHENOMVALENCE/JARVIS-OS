import tempfile
import unittest
from pathlib import Path

from jarvis_os.live_transcribe import LiveTranscriber
from jarvis_os.settings_cache import CachedSettings
from jarvis_os.storage import Database, SettingsRepository


class CachedSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.raw = SettingsRepository(Database(Path(self.temp.name) / "jarvis.db"))
        self.cached = CachedSettings(self.raw)

    def tearDown(self):
        self.temp.cleanup()

    def test_reads_match_the_underlying_repository(self):
        self.assertEqual(self.cached.get("speak_responses"), self.raw.get("speak_responses"))
        self.assertEqual(self.cached.get("ollama_model"), self.raw.get("ollama_model"))

    def test_writes_go_through_and_are_visible_immediately(self):
        self.cached.set("speak_responses", False)
        self.assertFalse(self.cached.get("speak_responses"))
        self.assertFalse(self.raw.get("speak_responses"))

    def test_unknown_keys_fall_back_to_the_supplied_default(self):
        self.assertEqual(self.cached.get("not_a_real_setting", "fallback"), "fallback")

    def test_all_reflects_writes(self):
        self.cached.set("mic_energy", 321)
        self.assertEqual(self.cached.all()["mic_energy"], 321)

    def test_refresh_picks_up_a_change_made_behind_the_cache(self):
        self.cached.get("mic_energy")
        self.raw.set("mic_energy", 456)
        self.assertNotEqual(self.cached.get("mic_energy"), 456)
        self.cached.refresh()
        self.assertEqual(self.cached.get("mic_energy"), 456)

    def test_defaults_are_exposed_for_settings_import_validation(self):
        self.assertIn("speak_responses", self.cached.DEFAULTS)

    def test_reads_do_not_touch_the_database_after_the_first(self):
        self.cached.get("speak_responses")
        opened = []
        original = self.raw.get

        def counting(key, default=None):
            opened.append(key)
            return original(key, default)

        self.raw.get = counting
        for _ in range(50):
            self.cached.get("speak_responses")
        self.assertEqual(opened, [])


class TranscriberReuseTests(unittest.TestCase):
    """A rebuilt transcriber loses its loaded models, which cost 2.35s to reload."""

    def test_same_models_produce_the_same_signature(self):
        first = LiveTranscriber(model="base", partial_model="tiny", energy=180)
        second = LiveTranscriber(model="base", partial_model="tiny", energy=400)
        self.assertEqual(first.signature(), second.signature())

    def test_changing_a_model_changes_the_signature(self):
        first = LiveTranscriber(model="base", partial_model="tiny")
        self.assertNotEqual(first.signature(), LiveTranscriber(model="small", partial_model="tiny").signature())
        self.assertNotEqual(first.signature(), LiveTranscriber(model="base", partial_model="base").signature())

    def test_changing_the_microphone_changes_the_signature(self):
        self.assertNotEqual(
            LiveTranscriber(device_index=None).signature(),
            LiveTranscriber(device_index=2).signature(),
        )

    def test_apply_adopts_tuning_without_dropping_models(self):
        live = LiveTranscriber(energy=180, pause=1.25)
        live._models["base"] = object()
        loaded = live._models["base"]
        live.apply(LiveTranscriber(energy=400, pause=2.0))
        self.assertEqual(live.energy, 400)
        self.assertEqual(live.pause, 2.0)
        self.assertIs(live._models["base"], loaded)


if __name__ == "__main__":
    unittest.main()

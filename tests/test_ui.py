import unittest

from jarvis_os.audio_level import NOISE_FLOOR, MicrophoneLevel, normalise, suggested_energy
from jarvis_os.theme import Palette, blend, state_style


class LevelNormalisationTests(unittest.TestCase):
    def test_silence_reads_as_zero(self):
        self.assertEqual(normalise(0), 0.0)
        self.assertEqual(normalise(NOISE_FLOOR), 0.0)

    def test_speech_lands_in_a_useful_middle_range(self):
        self.assertGreater(normalise(2500), 0.5)
        self.assertLess(normalise(2500), 1.0)

    def test_loud_input_is_clamped(self):
        self.assertEqual(normalise(50000), 1.0)

    def test_response_increases_monotonically(self):
        readings = [normalise(value) for value in (100, 300, 900, 2000, 5000)]
        self.assertEqual(readings, sorted(readings))


class CalibrationTests(unittest.TestCase):
    def test_threshold_clears_room_tone_without_going_deaf(self):
        quiet = suggested_energy(40)
        noisy = suggested_energy(300)
        self.assertGreater(noisy, quiet)
        self.assertGreaterEqual(quiet, 120)
        self.assertLessEqual(noisy, 500)

    def test_extreme_rooms_stay_within_usable_bounds(self):
        self.assertEqual(suggested_energy(0), 120)
        self.assertEqual(suggested_energy(99999), 500)


class MicrophoneLevelTests(unittest.TestCase):
    def test_reports_zero_and_stays_unavailable_without_a_device(self):
        levels = []
        monitor = MicrophoneLevel(levels.append)
        monitor._open = lambda: (_ for _ in ()).throw(OSError("no input device"))
        monitor._run()
        self.assertFalse(monitor.available)
        self.assertIn("no input device", monitor.error)
        self.assertEqual(levels, [0.0])

    def test_stop_is_safe_before_start(self):
        MicrophoneLevel(lambda _level: None).stop()


class ThemeTests(unittest.TestCase):
    def test_blend_produces_a_midpoint(self):
        self.assertEqual(blend("#000000", "#ffffff", 0.5), "#808080")

    def test_blend_clamps_out_of_range_amounts(self):
        self.assertEqual(blend("#000000", "#ffffff", -3), "#000000")
        self.assertEqual(blend("#000000", "#ffffff", 9), "#ffffff")

    def test_every_state_has_a_label_and_colour(self):
        for state in ("idle", "listening", "thinking", "speaking", "error"):
            label, colour = state_style(state)
            self.assertTrue(label.isupper())
            self.assertTrue(colour.startswith("#"))

    def test_unknown_state_still_renders(self):
        label, colour = state_style("indexing")
        self.assertEqual(label, "INDEXING")
        self.assertEqual(colour, Palette.ACCENT)


if __name__ == "__main__":
    unittest.main()

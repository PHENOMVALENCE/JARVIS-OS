import unittest

from jarvis_os.wake_word import WakeWordListener


class WakeWordTests(unittest.TestCase):
    def test_missing_access_key_fails_closed(self):
        listener = WakeWordListener("", lambda: None)
        self.assertFalse(listener.start())
        self.assertIsNone(listener.thread)

    def test_sensitivity_is_clamped(self):
        listener = WakeWordListener("key", lambda: None, sensitivity=1.8)
        self.assertEqual(listener.sensitivity, 1.0)


if __name__ == "__main__":
    unittest.main()


class BackendSelectionTests(unittest.TestCase):
    def test_prefers_the_keyless_backend(self):
        from jarvis_os.wake_word import OpenWakeWordListener, make_wake_word
        listener = make_wake_word(lambda: None)
        self.assertIsInstance(listener, OpenWakeWordListener)
        self.assertEqual(listener.keyword, "hey_jarvis")

    def test_uses_porcupine_when_explicitly_configured_with_a_key(self):
        from jarvis_os.wake_word import WakeWordListener, make_wake_word
        listener = make_wake_word(lambda: None, access_key="secret", backend="porcupine")
        self.assertIsInstance(listener, WakeWordListener)

    def test_porcupine_without_a_key_falls_back_to_the_keyless_backend(self):
        from jarvis_os.wake_word import OpenWakeWordListener, make_wake_word
        listener = make_wake_word(lambda: None, access_key="", backend="porcupine")
        self.assertIsInstance(listener, OpenWakeWordListener)

    def test_sensitivity_maps_to_a_detection_threshold(self):
        from jarvis_os.wake_word import OpenWakeWordListener
        self.assertAlmostEqual(OpenWakeWordListener(lambda: None, sensitivity=0.9).threshold, 0.1)
        self.assertAlmostEqual(OpenWakeWordListener(lambda: None, sensitivity=0.1).threshold, 0.9)

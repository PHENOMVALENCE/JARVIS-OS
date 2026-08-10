import unittest

from jarvis_os.wake_word import WakeWordListener


class WakeWordTests(unittest.TestCase):
    def test_missing_access_key_fails_closed(self):
        listener = WakeWordListener("", lambda: None)
        self.assertFalse(listener.start())
        self.assertIsNone(listener.thread)


if __name__ == "__main__":
    unittest.main()

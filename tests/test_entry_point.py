import unittest
from unittest.mock import Mock, patch

import Mark_7


class SingleInstanceTests(unittest.TestCase):
    """A second launch must show the running instance, not vanish."""

    def _with_mutex(self, already_exists: bool):
        kernel32 = Mock()
        kernel32.CreateMutexW.return_value = 1
        kernel32.GetLastError.return_value = 183 if already_exists else 0
        return kernel32

    def test_the_first_launch_starts_the_application(self):
        with patch("ctypes.windll") as windll, \
             patch("jarvis_os.app.run") as run:
            windll.kernel32 = self._with_mutex(already_exists=False)
            Mark_7.main()
        run.assert_called_once()

    def test_a_second_launch_raises_the_existing_window(self):
        with patch("ctypes.windll") as windll, \
             patch("jarvis_os.app.run") as run, \
             patch.object(Mark_7, "_raise_existing_window") as raise_window:
            windll.kernel32 = self._with_mutex(already_exists=True)
            Mark_7.main()
        raise_window.assert_called_once()
        run.assert_not_called()

    def test_a_failure_to_raise_the_window_is_not_fatal(self):
        with patch("ctypes.windll") as windll:
            windll.user32.EnumWindows.side_effect = OSError("no desktop")
            Mark_7._raise_existing_window()  # must not raise

    def test_the_self_test_runs_instead_when_asked(self):
        with patch.dict("os.environ", {"JARVIS_SELFTEST": "1"}), \
             patch("jarvis_os.selftest.run", return_value=0) as selftest, \
             self.assertRaises(SystemExit) as exit_code:
            Mark_7.main()
        selftest.assert_called_once()
        self.assertEqual(exit_code.exception.code, 0)


if __name__ == "__main__":
    unittest.main()

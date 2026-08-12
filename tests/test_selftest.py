import io
import unittest
from unittest.mock import patch

from jarvis_os.selftest import SUBSYSTEMS, run


class SelfTestTests(unittest.TestCase):
    """The build gate. It has to fail loudly when the bundle is incomplete."""

    def test_a_complete_environment_passes(self):
        stream = io.StringIO()
        self.assertEqual(run(stream), 0)
        self.assertIn("All", stream.getvalue())

    def test_a_missing_dependency_fails_the_build(self):
        real = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def refuse(name, *args, **kwargs):
            if name == "openwakeword":
                raise ImportError("DLL load failed")
            return real(name, *args, **kwargs)

        stream = io.StringIO()
        with patch("builtins.__import__", side_effect=refuse):
            code = run(stream)
        self.assertEqual(code, 1)
        self.assertIn("openwakeword", stream.getvalue())

    def test_the_reason_is_reported_not_just_the_name(self):
        real = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def refuse(name, *args, **kwargs):
            if name == "onnxruntime":
                raise ImportError("DLL load failed while importing onnxruntime_pybind11_state")
            return real(name, *args, **kwargs)

        stream = io.StringIO()
        with patch("builtins.__import__", side_effect=refuse):
            run(stream)
        self.assertIn("DLL load failed", stream.getvalue())

    def test_onnxruntime_is_loaded_before_the_windows_runtime(self):
        """Order matters: WinRT first breaks onnxruntime's DLL load."""
        names = [module for module, _purpose in SUBSYSTEMS]
        self.assertLess(names.index("onnxruntime"), names.index("winrt.windows.media.ocr"))

    def test_every_subsystem_states_why_it_is_needed(self):
        for module, purpose in SUBSYSTEMS:
            self.assertTrue(purpose, module)


if __name__ == "__main__":
    unittest.main()

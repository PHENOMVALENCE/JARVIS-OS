import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jarvis_os import startup
from jarvis_os.storage import Database, SettingsRepository


class StartupTests(unittest.TestCase):
    def test_uses_the_scheduled_task_script_when_present(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Install-Startup.ps1").write_text("", encoding="utf-8")
            with patch.object(startup, "_run_script", return_value=(True, "ok")) as runner:
                succeeded, _message = startup.set_startup(True, root)
            self.assertTrue(succeeded)
            self.assertEqual(runner.call_args.args[0].name, "Install-Startup.ps1")

    def test_disabling_uses_the_removal_script(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Remove-Startup.ps1").write_text("", encoding="utf-8")
            with patch.object(startup, "_run_script", return_value=(True, "ok")) as runner:
                startup.set_startup(False, root)
            self.assertEqual(runner.call_args.args[0].name, "Remove-Startup.ps1")

    def test_falls_back_to_the_run_key_without_scripts(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(startup, "_set_run_key", return_value=(True, "ok")) as fallback:
                startup.set_startup(True, Path(folder))
            fallback.assert_called_once_with(True)

    def test_reports_failure_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Install-Startup.ps1").write_text("", encoding="utf-8")
            with patch.object(startup, "_run_script", return_value=(False, "access denied")):
                succeeded, message = startup.set_startup(True, root)
        self.assertFalse(succeeded)
        self.assertIn("access denied", message)


class WizardChoiceTests(unittest.TestCase):
    """The wizard's saving logic, exercised without building any windows."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = SettingsRepository(Database(Path(self.temp.name) / "jarvis.db"))

    def tearDown(self):
        self.temp.cleanup()

    def _finish(self, **choices):
        from jarvis_os.setup_ui import SetupWizard

        wizard = Mock(spec=SetupWizard)
        wizard.settings = self.settings
        wizard.project_root = Path(self.temp.name)
        wizard.calibrated_energy = choices.pop("calibrated_energy", None)
        wizard._leave_step = Mock()
        wizard.destroy = Mock()
        wizard.finish_status = None
        defaults = {"wake_word": True, "speak": True, "memory": True,
                    "proactive": True, "privacy": False, "offline_voice": False,
                    "autostart": False}
        defaults.update(choices)
        for name, value in defaults.items():
            setattr(wizard, name, Mock(get=Mock(return_value=value)))
        # setup_ui imports the name directly, so patch it where it is used.
        with patch("jarvis_os.setup_ui.set_startup", return_value=(True, "ok")):
            SetupWizard.finish(wizard)
        return wizard

    def test_wake_word_choice_is_saved(self):
        self._finish(wake_word=True)
        self.assertTrue(self.settings.get("wake_word_enabled"))
        self._finish(wake_word=False)
        self.assertFalse(self.settings.get("wake_word_enabled"))

    def test_offline_voice_selects_the_piper_engine(self):
        self._finish(offline_voice=True)
        self.assertEqual(self.settings.get("tts_engine"), "piper")
        self._finish(offline_voice=False)
        self.assertEqual(self.settings.get("tts_engine"), "edge")

    def test_calibration_result_is_applied(self):
        self._finish(calibrated_energy=214)
        self.assertEqual(self.settings.get("mic_energy"), 214)

    def test_skipping_calibration_leaves_the_default(self):
        self._finish()
        self.assertEqual(self.settings.get("mic_energy"), 180)

    def test_setup_is_marked_complete(self):
        self._finish()
        self.assertTrue(self.settings.get("first_run_complete"))

    def test_startup_is_enabled_when_chosen(self):
        self._finish(autostart=True)
        self.assertTrue(self.settings.get("startup_enabled"))

    def test_startup_is_recorded_only_when_it_succeeds(self):
        from jarvis_os.setup_ui import SetupWizard

        self._finish(autostart=False)
        self.assertFalse(self.settings.get("startup_enabled"))

        wizard = Mock(spec=SetupWizard)
        wizard.settings = self.settings
        wizard.project_root = Path(self.temp.name)
        wizard.calibrated_energy = None
        wizard._leave_step = Mock()
        wizard.destroy = Mock()
        wizard.finish_status = None
        for name in ("wake_word", "speak", "memory", "proactive", "privacy", "offline_voice"):
            setattr(wizard, name, Mock(get=Mock(return_value=True)))
        wizard.autostart = Mock(get=Mock(return_value=True))
        with patch("jarvis_os.setup_ui.set_startup", return_value=(False, "denied")):
            SetupWizard.finish(wizard)
        self.assertFalse(self.settings.get("startup_enabled"))


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jarvis_os.capabilities import build_registry
from jarvis_os.hardware import PROFILES, Hardware
from jarvis_os.models import InstallResult, ModelManager, OllamaModels
from jarvis_os.recovery_state import InstanceLock, RecoveryState


def machine(total=16.0, disk=100.0):
    return Hardware(system="Windows", release="11", architecture="AMD64", processor="x86",
                    cores=8, total_ram_gb=total, available_ram_gb=8.0, free_disk_gb=disk)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.registry = build_registry()

    def tearDown(self):
        self.temp.cleanup()

    def test_a_clean_shutdown_is_not_reported_as_a_crash(self):
        state = RecoveryState(self.dir)
        state.begin()
        state.finish()
        self.assertIsNone(RecoveryState(self.dir).begin())

    def test_a_missing_shutdown_marker_is_treated_as_a_crash(self):
        RecoveryState(self.dir).begin()  # never finishes
        crashed = RecoveryState(self.dir).begin()
        self.assertIsNotNone(crashed)
        self.assertTrue(crashed.crashed)

    def test_a_first_ever_run_is_not_a_crash(self):
        self.assertIsNone(RecoveryState(self.dir).begin())

    def test_the_action_in_flight_is_remembered(self):
        state = RecoveryState(self.dir)
        state.begin()
        state.note_in_flight("delete_path", "notes.txt")
        crashed = RecoveryState(self.dir).begin()
        self.assertEqual(crashed.in_flight, "delete_path")
        self.assertIn("notes.txt", crashed.in_flight_detail)

    def test_a_completed_action_is_no_longer_in_flight(self):
        state = RecoveryState(self.dir)
        state.begin()
        state.note_in_flight("delete_path", "notes.txt")
        state.clear_in_flight()
        self.assertEqual(RecoveryState(self.dir).begin().in_flight, "")

    def test_destructive_work_is_never_offered_for_retry(self):
        for action in ("delete_path", "install_package", "type_text", "close_app",
                       "clear_reminders"):
            self.assertFalse(RecoveryState.safe_to_repeat(action, self.registry), action)

    def test_read_only_work_may_be_repeated(self):
        for action in ("current_time", "find_files", "weather", "web_research"):
            self.assertTrue(RecoveryState.safe_to_repeat(action, self.registry), action)

    def test_an_unknown_action_is_never_repeated(self):
        self.assertFalse(RecoveryState.safe_to_repeat("mystery_action", self.registry))

    def test_the_report_warns_rather_than_retrying_destructive_work(self):
        state = RecoveryState(self.dir)
        state.begin()
        state.note_in_flight("delete_path", "notes.txt")
        following = RecoveryState(self.dir)
        following.begin()
        report = following.report(self.registry)
        self.assertIn("not safe to repeat", report)
        self.assertIn("delete_path", report)

    def test_the_report_is_empty_after_a_clean_run(self):
        state = RecoveryState(self.dir)
        state.begin()
        state.finish()
        following = RecoveryState(self.dir)
        following.begin()
        self.assertEqual(following.report(self.registry), "")

    def test_corrupt_state_does_not_prevent_starting(self):
        (self.dir / "session.json").write_text("{ not json", encoding="utf-8")
        RecoveryState(self.dir).begin()  # must not raise


class InstanceLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_a_lock_can_be_claimed_when_none_exists(self):
        self.assertTrue(InstanceLock(self.dir).claim())

    def test_a_lock_held_by_a_live_process_is_not_stolen(self):
        lock = InstanceLock(self.dir)
        lock.claim()
        other = InstanceLock(self.dir)
        other._process_alive = lambda _pid: True
        self.assertFalse(other.claim())

    def test_a_lock_left_by_a_dead_process_is_cleared(self):
        (self.dir / "instance.lock").write_text(json.dumps({"pid": 999999, "at": 0}), encoding="utf-8")
        lock = InstanceLock(self.dir)
        lock._process_alive = lambda _pid: False
        self.assertTrue(lock.stale())
        self.assertTrue(lock.claim())

    def test_a_corrupt_lock_is_treated_as_stale(self):
        (self.dir / "instance.lock").write_text("nonsense", encoding="utf-8")
        self.assertTrue(InstanceLock(self.dir).stale())

    def test_releasing_only_removes_our_own_lock(self):
        (self.dir / "instance.lock").write_text(json.dumps({"pid": 4242, "at": 0}), encoding="utf-8")
        InstanceLock(self.dir).release()
        self.assertTrue((self.dir / "instance.lock").exists())


class ModelManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.language = Mock()
        self.speech = Mock()
        self.voices = Mock()
        self.settings = Mock()
        self.settings.get.side_effect = lambda key, default=None: default
        self.manager = ModelManager(Path(self.temp.name), self.settings,
                                    self.language, self.speech, self.voices, machine())

    def tearDown(self):
        self.temp.cleanup()

    def test_the_plan_states_the_download_size_before_spending_it(self):
        self.language.has.return_value = False
        self.speech.installed.return_value = False
        needed, size = self.manager.plan(PROFILES[1])
        self.assertEqual(len(needed), 2)
        self.assertGreater(size, 4.0)
        self.assertIn("GB to download", self.manager.describe_plan(PROFILES[1]))

    def test_nothing_to_do_is_said_plainly(self):
        self.language.has.return_value = True
        self.speech.installed.return_value = True
        self.assertIn("already installed", self.manager.describe_plan(PROFILES[1]))

    def test_a_profile_too_large_for_the_machine_is_refused(self):
        small = ModelManager(Path(self.temp.name), self.settings,
                             self.language, self.speech, self.voices, machine(total=4))
        result = small.install(PROFILES[2])
        self.assertFalse(result.succeeded)
        self.language.pull.assert_not_called()

    def test_a_full_disk_is_refused_before_downloading(self):
        full = ModelManager(Path(self.temp.name), self.settings,
                            self.language, self.speech, self.voices, machine(disk=1.0))
        self.assertFalse(full.install(PROFILES[1]).succeeded)
        self.language.pull.assert_not_called()

    def test_a_failed_recognition_download_stops_before_the_language_model(self):
        self.speech.ensure.return_value = InstallResult(False, "no network")
        result = self.manager.install(PROFILES[0])
        self.assertFalse(result.succeeded)
        self.language.pull.assert_not_called()

    def test_a_successful_install_records_the_choice(self):
        self.speech.ensure.return_value = InstallResult(True, "ready")
        self.language.pull.return_value = InstallResult(True, "ready")
        self.assertTrue(self.manager.install(PROFILES[0]).succeeded)
        written = {call.args[0]: call.args[1] for call in self.settings.set.call_args_list}
        self.assertEqual(written["ollama_model"], PROFILES[0].model)
        self.assertEqual(written["whisper_model"], PROFILES[0].speech_model)

    def test_health_reports_a_missing_runtime_rather_than_a_failure(self):
        self.language.available = False
        self.assertEqual(self.manager.health()["status"], "NOT CONFIGURED")

    def test_health_reports_a_missing_download_as_degraded(self):
        self.language.available = True
        self.language.has.return_value = False
        self.speech.installed.return_value = True
        self.assertEqual(self.manager.health()["status"], "DEGRADED")


class OllamaModelsTests(unittest.TestCase):
    def test_a_missing_runtime_is_reported_not_raised(self):
        models = OllamaModels()
        with patch("shutil.which", return_value=None):
            result = models.pull("gemma2:2b")
        self.assertFalse(result.succeeded)
        self.assertIn("ollama.com", result.message)

    def test_an_installed_model_is_not_downloaded_again(self):
        models = OllamaModels()
        models.has = lambda _m: True
        with patch("shutil.which", return_value="ollama"):
            result = models.pull("gemma2:2b")
        self.assertTrue(result.already_present)

    def test_listing_survives_the_service_being_down(self):
        models = OllamaModels()
        with patch("shutil.which", return_value="ollama"), \
             patch.object(OllamaModels, "_run", side_effect=OSError("service down")):
            self.assertEqual(models.installed(), ())


if __name__ == "__main__":
    unittest.main()

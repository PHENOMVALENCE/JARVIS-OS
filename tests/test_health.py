import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jarvis_os.hardware import Hardware, ModelProfile, fits, pressure_warning, recommend, summary
from jarvis_os.health import Check, HealthService, Status


def machine(total=16.0, available=8.0, disk=100.0, gpu="", vram=0.0):
    return Hardware(system="Windows", release="11", architecture="AMD64", processor="x86",
                    cores=8, total_ram_gb=total, available_ram_gb=available,
                    free_disk_gb=disk, gpu=gpu, vram_gb=vram)


class RecommendationTests(unittest.TestCase):
    def test_a_small_machine_gets_the_lightweight_profile(self):
        self.assertEqual(recommend(machine(total=8)).name, "Lightweight")

    def test_a_typical_machine_gets_the_standard_profile(self):
        self.assertEqual(recommend(machine(total=16)).name, "Standard")

    def test_a_large_machine_gets_the_performance_profile(self):
        self.assertEqual(recommend(machine(total=32)).name, "Performance")

    def test_a_capable_gpu_lifts_the_recommendation(self):
        self.assertEqual(recommend(machine(total=16, gpu="RTX 4070", vram=12)).name, "Performance")

    def test_the_recommendation_ignores_momentary_free_memory(self):
        """A browser closing should not change which model is configured."""
        busy = recommend(machine(total=16, available=1.0))
        idle = recommend(machine(total=16, available=14.0))
        self.assertEqual(busy.name, idle.name)


class FitTests(unittest.TestCase):
    def setUp(self):
        self.profile = ModelProfile("Standard", "llama3.1:8b", 4.7, 6.0, "base", "")

    def test_refuses_when_the_disk_is_too_full(self):
        ok, why = fits(self.profile, machine(disk=3.0))
        self.assertFalse(ok)
        self.assertIn("free", why)

    def test_refuses_when_there_is_not_enough_memory(self):
        ok, why = fits(self.profile, machine(total=6))
        self.assertFalse(ok)
        self.assertIn("memory", why)

    def test_accepts_a_capable_machine(self):
        self.assertTrue(fits(self.profile, machine())[0])

    def test_warns_when_the_machine_is_busy_rather_than_small(self):
        warning = pressure_warning(machine(total=16, available=1.1), self.profile)
        self.assertIn("closing some windows", warning.lower())

    def test_no_warning_when_memory_is_free(self):
        self.assertEqual(pressure_warning(machine(total=16, available=12.0), self.profile), "")

    def test_summary_reads_as_a_sentence(self):
        self.assertIn("no discrete GPU", summary(machine()))
        self.assertIn("RTX 4070", summary(machine(gpu="RTX 4070", vram=12)))


class HealthCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Mock()
        self.settings.get.side_effect = lambda key, default=None: {
            "wake_word_enabled": True, "privacy_mode": False, "tts_engine": "edge",
            "whisper_model": "base", "partial_whisper_model": "tiny",
            "ollama_model": "gemma2:2b",
        }.get(key, default)
        self.service = HealthService(self.settings, Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_a_disabled_feature_is_disabled_not_broken(self):
        self.settings.get.side_effect = lambda key, default=None: (
            False if key == "wake_word_enabled" else default
        )
        check = self.service.check_wake_word()
        self.assertIs(check.status, Status.DISABLED)
        self.assertTrue(check.remedy)

    def test_privacy_mode_disables_screen_reading_rather_than_failing_it(self):
        self.settings.get.side_effect = lambda key, default=None: (
            True if key == "privacy_mode" else default
        )
        with patch("jarvis_os.ocr.ScreenTextReader.available", return_value=True):
            self.assertIs(self.service.check_screen_reading().status, Status.DISABLED)

    def test_a_missing_model_is_degraded_with_the_command_to_fix_it(self):
        with patch("shutil.which", return_value="ollama"), \
             patch("subprocess.run") as run:
            run.return_value = Mock(returncode=0, stdout="llama3.1:8b\n")
            check = self.service.check_language_model()
        self.assertIs(check.status, Status.DEGRADED)
        self.assertIn("ollama pull", check.remedy)

    def test_a_missing_runtime_is_not_configured_rather_than_failed(self):
        with patch("shutil.which", return_value=None):
            self.assertIs(self.service.check_language_model().status, Status.NOT_CONFIGURED)

    def test_a_broken_check_is_reported_not_swallowed(self):
        self.service.check_microphone = Mock(side_effect=OSError("audio stack gone"))
        statuses = [check.status for check in self.service.run()]
        self.assertIn(Status.FAILED, statuses)

    def test_a_healthy_system_summarises_in_one_line(self):
        checks = [Check("Microphone", Status.OK, "fine"), Check("Disk", Status.OK, "fine")]
        self.assertIn("healthy", self.service.summarise(checks))

    def test_the_summary_leads_with_a_problem_and_its_remedy(self):
        checks = [
            Check("Microphone", Status.OK, "fine"),
            Check("Language model", Status.DEGRADED, "gemma2:2b is not downloaded.",
                  "Run: ollama pull gemma2:2b"),
        ]
        summary_text = self.service.summarise(checks)
        self.assertIn("language model", summary_text)
        self.assertIn("ollama pull", summary_text)

    def test_disabled_subsystems_do_not_count_as_problems(self):
        checks = [Check("Wake word", Status.DISABLED, "off"), Check("Disk", Status.OK, "fine")]
        self.assertIn("healthy", self.service.summarise(checks))

    def test_every_check_returns_a_known_status(self):
        for check in self.service.run():
            self.assertIsInstance(check.status, Status)
            self.assertTrue(check.subsystem)

class OnnxOrderingRegressionTests(unittest.TestCase):
    """Reading the screen must not disable the wake word.

    Initialising the Windows Runtime before onnxruntime has loaded makes the
    first onnxruntime DLL load fail, which silently took out both the wake word
    and the offline voice. The OCR reader preloads onnxruntime to prevent it.
    """

    def test_ocr_preloads_onnxruntime_before_touching_winrt(self):
        from jarvis_os.ocr import ScreenTextReader

        order = []
        with patch("jarvis_os.ocr.ScreenTextReader._preload_onnxruntime",
                   side_effect=lambda: order.append("onnx")):
            try:
                ScreenTextReader._engine()
            except Exception:
                pass
        self.assertEqual(order, ["onnx"], "WinRT was initialised without preloading onnxruntime")

    def test_preloading_survives_onnxruntime_being_absent(self):
        from jarvis_os.ocr import ScreenTextReader

        with patch.dict("sys.modules", {"onnxruntime": None}):
            ScreenTextReader._preload_onnxruntime()  # must not raise
class ModelHealthTests(unittest.TestCase):
    def _service(self, models):
        settings = Mock()
        settings.get.side_effect = lambda key, default=None: default
        return HealthService(settings, Path(tempfile.gettempdir()), models=models)

    def test_no_manager_is_not_configured_rather_than_failed(self):
        self.assertIs(self._service(None).check_models().status, Status.NOT_CONFIGURED)

    def test_a_missing_download_is_degraded_with_a_way_forward(self):
        models = Mock()
        models.health.return_value = {"status": "DEGRADED", "detail": "Not downloaded: llama3.1:8b"}
        check = self._service(models).check_models()
        self.assertIs(check.status, Status.DEGRADED)
        self.assertTrue(check.remedy)

    def test_a_missing_runtime_points_at_ollama(self):
        models = Mock()
        models.health.return_value = {"status": "NOT CONFIGURED", "detail": "Ollama is not installed."}
        self.assertIn("ollama.com", self._service(models).check_models().remedy)

    def test_everything_installed_reports_ok(self):
        models = Mock()
        models.health.return_value = {"status": "OK", "detail": "All configured models are installed."}
        self.assertIs(self._service(models).check_models().status, Status.OK)

if __name__ == "__main__":
    unittest.main()

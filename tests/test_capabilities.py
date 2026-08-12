import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from jarvis_os.actions import WindowsActions
from jarvis_os.capabilities import Capability, CapabilityRegistry, build_registry
from jarvis_os.commands import ActionResult, Command, Risk
from jarvis_os.router import CommandRouter
from jarvis_os.settings_ui import ACTIONS

# Router outcomes that steer the conversation rather than touching the machine.
CONTROL_FLOW = {"chat", "follow_up", "repeat_last"}


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = build_registry()

    def test_confirmation_follows_risk(self):
        self.assertEqual(self.registry.get("delete_path").confirmation, "always")
        self.assertEqual(self.registry.get("close_window").confirmation, "conditional")
        self.assertEqual(self.registry.get("current_time").confirmation, "never")

    def test_destructive_actions_are_marked_reversible_where_they_are(self):
        self.assertTrue(self.registry.get("delete_path").reversible)

    def test_cloud_capabilities_are_flagged(self):
        self.assertIn("analyze_screen", self.registry.requiring_network())
        self.assertIn("weather", self.registry.requiring_network())
        self.assertNotIn("current_time", self.registry.requiring_network())

    def test_local_fast_paths_need_no_permission(self):
        for action in ("current_time", "current_date", "calculate", "convert"):
            self.assertEqual(self.registry.get(action).permissions, (), action)

    def test_registering_a_duplicate_is_refused(self):
        registry = CapabilityRegistry()
        registry.register(Capability("demo", "Demo"))
        with self.assertRaises(ValueError):
            registry.register(Capability("demo", "Demo again"))

    def test_a_plugin_can_replace_a_capability_deliberately(self):
        registry = CapabilityRegistry()
        registry.register(Capability("demo", "Demo"))
        registry.register(Capability("demo", "Replaced", owner="plugin"), replace=True)
        self.assertEqual(registry.get("demo").owner, "plugin")

    def test_describe_returns_the_metadata_a_ui_needs(self):
        described = self.registry.describe("delete_path")
        self.assertEqual(described["risk"], "high")
        self.assertTrue(described["reversible"])
        self.assertIn("files.write", described["permissions"])

    def test_unknown_actions_describe_as_nothing(self):
        self.assertEqual(self.registry.describe("not_an_action"), {})


class RegistryMatchesRouterTests(unittest.TestCase):
    """The registry is the source of truth, so the router must agree with it."""

    SPOKEN = [
        "Open Notepad", "Close Spotify", "Close this", "Minimise this",
        "Take a screenshot", "Read the screen", "What is on my screen",
        "Delete file notes.txt", "Undo that", "Find the budget",
        "What time is it", "What is the date", "What is 2+2", "10 km in miles",
        "How is my battery", "How much disk space do I have",
        "What is the weather", "Weather forecast for London",
        "Research battery technology", "Search the internet for cats",
        "Search my documents for the plan", "Index my documents",
        "Remind me in 10 minutes to call", "What reminders do I have",
        "Cancel all reminders", "What is playing", "Play some music",
        "Pause", "Volume 40", "Volume up", "Type hello", "Read clipboard",
        "Switch to Notepad", "Minimize Notepad", "Start work mode",
        "Read the Notepad window", "Click Save in Notepad",
        "Install package VideoLAN.VLC", "What went wrong",
        "What am I doing", "Open the folder this file is in",
        "Show notification hello", "Copy this text",
    ]

    def setUp(self):
        self.router = CommandRouter()
        self.registry = build_registry()

    def test_every_routed_action_is_registered(self):
        for text in self.SPOKEN:
            action = self.router.route(text).action
            if action in CONTROL_FLOW:
                continue
            self.assertIsNotNone(self.registry.get(action), f"{text!r} -> {action} is unregistered")

    def test_router_risk_matches_the_registry(self):
        """Catches the two drifting apart, which is how permissions get bypassed."""
        for text in self.SPOKEN:
            command = self.router.route(text)
            capability = self.registry.get(command.action)
            if capability is None:
                continue
            self.assertEqual(command.risk, capability.risk,
                             f"{text!r} -> {command.action}: router says {command.risk.value}, "
                             f"registry says {capability.risk.value}")

    def test_every_capability_can_be_permission_configured(self):
        for action in self.registry.actions():
            if action == "noop":
                continue
            self.assertIn(action, ACTIONS, f"{action} is missing from the permissions screen")


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.actions = WindowsActions(home=Path(self.temp.name), data_dir=Path(self.temp.name))
        self.actions.context = Mock()

    def tearDown(self):
        self.temp.cleanup()

    def test_a_claim_that_did_not_take_effect_becomes_a_failure(self):
        surviving = Path(self.temp.name) / "still-here.txt"
        surviving.write_text("here", encoding="utf-8")
        self.actions._handlers["delete_path"] = lambda _a: ActionResult(
            True, "Moved it to the Recycle Bin.", {"path": str(surviving)}
        )
        result = self.actions.execute(Command("delete_path", {"path": str(surviving)}))
        self.assertFalse(result.success)
        self.assertIn("did not take effect", result.message)

    def test_a_real_success_passes_verification(self):
        gone = Path(self.temp.name) / "gone.txt"
        self.actions._handlers["delete_path"] = lambda _a: ActionResult(
            True, "Moved it to the Recycle Bin.", {"path": str(gone)}
        )
        self.assertTrue(self.actions.execute(Command("delete_path", {"path": str(gone)})).success)

    def test_an_empty_result_set_is_not_reported_as_found(self):
        self.actions._handlers["find_files"] = lambda _a: ActionResult(True, "Found them.", {"matches": []})
        result = self.actions.execute(Command("find_files", {"query": "x"}))
        self.assertFalse(result.success)

    def test_failures_are_left_alone(self):
        self.actions._handlers["find_files"] = lambda _a: ActionResult(False, "Nothing matched.")
        result = self.actions.execute(Command("find_files", {"query": "x"}))
        self.assertEqual(result.message, "Nothing matched.")

    def test_a_broken_verifier_does_not_lose_the_result(self):
        self.actions.registry.register(
            Capability("find_files", "Find files",
                       verifier=Mock(side_effect=OSError("disk gone"))),
            replace=True,
        )
        self.actions._handlers["find_files"] = lambda _a: ActionResult(True, "Found 3.", {"matches": ["a"]})
        self.assertTrue(self.actions.execute(Command("find_files", {"query": "x"})).success)

    def test_unverifiable_actions_still_run(self):
        self.actions._handlers["current_time"] = lambda _a: ActionResult(True, "It's 9 PM.")
        self.assertTrue(self.actions.execute(Command("current_time")).success)

    def test_an_exception_becomes_a_reported_failure(self):
        self.actions._handlers["current_time"] = Mock(side_effect=OSError("clock broken"))
        result = self.actions.execute(Command("current_time"))
        self.assertFalse(result.success)
        self.assertIn("clock broken", result.message)


if __name__ == "__main__":
    unittest.main()

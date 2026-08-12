import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from jarvis_os.assistant import AssistantController, ConversationStore
from jarvis_os.commands import ActionResult
from jarvis_os.language import SWAHILI, detect, to_command_english, voice_for
from jarvis_os.router import CommandRouter


class DetectionTests(unittest.TestCase):
    def test_recognises_swahili(self):
        for text in ("fungua Notepad", "hali ya hewa leo ikoje", "saa ngapi sasa",
                     "nikumbushe baada ya dakika kumi", "tafuta mtandaoni maana ya AI"):
            self.assertEqual(detect(text), SWAHILI, text)

    def test_recognises_english(self):
        for text in ("open Notepad", "what is the weather today", "remind me in 10 minutes",
                     "play some music", "what time is it"):
            self.assertEqual(detect(text), "en", text)

    def test_empty_input_defaults_to_english(self):
        self.assertEqual(detect(""), "en")
        self.assertEqual(detect("12345"), "en")


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def _route(self, swahili: str) -> str:
        return self.router.route(to_command_english(swahili)).action

    def test_swahili_commands_reach_the_same_actions(self):
        self.assertEqual(self._route("fungua Notepad"), "open_app")
        self.assertEqual(self._route("saa ngapi sasa"), "current_time")
        self.assertEqual(self._route("hali ya hewa leo ikoje"), "weather")
        self.assertEqual(self._route("pandisha sauti"), "change_volume")
        self.assertEqual(self._route("picha ya skrini"), "screenshot")
        self.assertEqual(self._route("tafuta mtandaoni maana ya AI"), "web_research")

    def test_counts_that_follow_the_unit_are_reordered(self):
        self.assertIn("10 minutes", to_command_english("nikumbushe baada ya dakika kumi"))
        self.assertIn("2 hours", to_command_english("nikumbushe baada ya saa mbili"))

    def test_english_passes_through_untouched(self):
        self.assertEqual(to_command_english("open Notepad"), "open Notepad")


class VoiceSelectionTests(unittest.TestCase):
    def test_swahili_replies_use_a_swahili_voice(self):
        self.assertEqual(voice_for(SWAHILI, "edge", "en-GB-RyanNeural"), "sw-TZ-DaudiNeural")

    def test_english_keeps_whatever_the_user_chose(self):
        self.assertEqual(voice_for("en", "edge", "en-US-GuyNeural"), "en-US-GuyNeural")


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ConversationStore(Path(self.temp.name) / "conversation.db")
        self.executor = Mock()
        self.executor.execute.return_value = ActionResult(True, "Done.")
        self.provider = Mock()
        self.provider.reply.return_value = "Sawa."
        self.controller = AssistantController(self.executor, self.store, self.provider)

    def tearDown(self):
        self.temp.cleanup()

    def test_a_swahili_command_runs_the_english_action(self):
        self.controller.process("fungua Notepad")
        command = self.executor.execute.call_args.args[0]
        self.assertEqual(command.action, "open_app")
        self.assertEqual(self.controller.last_language, SWAHILI)

    def test_swahili_conversation_asks_for_a_swahili_reply(self):
        self.controller.process("niambie kuhusu Tanzania")
        messages = self.provider.reply.call_args.args[0]
        self.assertTrue(any("Kiswahili" in item["content"] for item in messages))

    def test_english_conversation_does_not(self):
        self.controller.process("tell me about Tanzania")
        messages = self.provider.reply.call_args.args[0]
        self.assertFalse(any("Kiswahili" in item["content"] for item in messages))

    def test_bilingual_handling_can_be_switched_off(self):
        settings = Mock()
        settings.get.side_effect = lambda key, default=None: (
            False if key == "bilingual_enabled" else default
        )
        controller = AssistantController(self.executor, self.store, self.provider, settings_repo=settings)
        controller.process("fungua Notepad")
        self.assertEqual(controller.last_language, "en")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from jarvis_os.assistant import AssistantController, ConversationStore, VoiceConfig, VoiceInput
from jarvis_os.commands import ActionResult


class AssistantControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ConversationStore(Path(self.temp.name) / "conversation.db")
        self.executor = Mock()
        self.executor.execute.return_value = ActionResult(True, "Opened spotify.")
        self.provider = Mock()
        self.provider.reply.return_value = "Hello there."
        self.controller = AssistantController(self.executor, self.store, self.provider)

    def tearDown(self):
        self.temp.cleanup()

    def test_local_action_does_not_call_model(self):
        reply = self.controller.process("Open Spotify")
        self.assertEqual(reply.text, "Opened spotify.")
        self.provider.reply.assert_not_called()

    def test_chat_is_persisted(self):
        reply = self.controller.process("How are you?")
        self.assertEqual(reply.text, "Hello there.")
        self.assertEqual([item["role"] for item in self.store.recent()], ["user", "assistant"])

    def test_spoken_chat_requests_conversational_output(self):
        self.controller.process("So, uh, explain that", spoken=True)
        messages = self.provider.reply.call_args.args[0]
        self.assertTrue(any("live spoken conversation" in item["content"] for item in messages))

    def test_voice_input_filters_silence_markers(self):
        self.assertEqual(VoiceInput.clean_transcript("  [BLANK_AUDIO]  "), "")
        self.assertEqual(VoiceInput.clean_transcript("open   Spotify"), "open Spotify")

    def test_chat_can_run_without_persistent_memory(self):
        settings = Mock()
        settings.get.return_value = False
        controller = AssistantController(self.executor, self.store, self.provider, settings_repo=settings)
        controller.process("Do not remember this")
        self.assertEqual(self.store.recent(), [])

    def test_document_search_synthesizes_cited_answer(self):
        self.executor.execute.return_value = ActionResult(
            True, "Found passages.", {"matches": ["C:\\docs\\plan.pdf#page=2\nLaunch budget is 12000"]}
        )
        reply = self.controller.process("Search my documents for launch budget")
        self.assertEqual(reply.text, "Hello there.")
        self.provider.reply.assert_called_once()
        self.assertIn("plan.pdf#page=2", self.provider.reply.call_args.args[0][1]["content"])

    def test_time_sensitive_question_is_answered_from_live_sources(self):
        self.executor.execute.return_value = ActionResult(
            True, "Found web sources.", {"matches": ["SOURCE: Met\nURL: https://met.example\nSUMMARY: 24C and clear"]}
        )
        reply = self.controller.process("What is the weather today")
        self.assertEqual(self.executor.execute.call_args.args[0].action, "web_research")
        self.assertEqual(reply.text, "Hello there.")
        self.assertIn("https://met.example", self.provider.reply.call_args.args[0][1]["content"])

    def test_timeless_question_stays_conversational(self):
        self.controller.process("What is the meaning of AI")
        self.executor.execute.assert_not_called()
        self.provider.reply.assert_called_once()

    def test_failed_automatic_search_falls_back_to_conversation(self):
        self.executor.execute.return_value = ActionResult(False, "Web research failed: no internet.")
        reply = self.controller.process("What is the weather today")
        self.assertEqual(reply.text, "Hello there.")
        self.assertNotIn("failed", reply.text)

    def test_automatic_search_can_be_disabled(self):
        settings = Mock()
        settings.get.side_effect = lambda key, default=None: False if key == "auto_web_answers" else default
        controller = AssistantController(self.executor, self.store, self.provider, settings_repo=settings)
        controller.process("What is the weather today")
        self.executor.execute.assert_not_called()

    def test_web_research_synthesizes_source_grounded_answer(self):
        self.executor.execute.return_value = ActionResult(
            True, "Found web sources.", {"matches": ["SOURCE: Example\nURL: https://example.com\nSUMMARY: Current facts"]}
        )
        reply = self.controller.process("Research current battery technology")
        self.assertEqual(reply.text, "Hello there.")
        self.assertIn("https://example.com", self.provider.reply.call_args.args[0][1]["content"])


class VoiceInputTests(unittest.TestCase):
    def _voice(self, transcripts, **overrides):
        voice = VoiceInput(VoiceConfig(**overrides))
        voice._ensure_microphone = lambda: None
        voice._microphone = Mock()
        voice._microphone.listen.side_effect = transcripts
        return voice

    def test_extended_listening_joins_speech_split_by_a_pause(self):
        voice = self._voice(["open the", "budget spreadsheet", ""], continuation_passes=2)
        self.assertEqual(voice.listen(), "open the budget spreadsheet")

    def test_extended_listening_stops_at_the_first_silence(self):
        voice = self._voice(["hello there", "", "ignored"], continuation_passes=2)
        self.assertEqual(voice.listen(), "hello there")

    def test_extended_listening_can_be_disabled(self):
        voice = self._voice(["hello there", "extra"], extended_listening=False)
        self.assertEqual(voice.listen(), "hello there")

    def test_silence_markers_never_start_a_phrase(self):
        voice = self._voice(["[BLANK_AUDIO]"])
        self.assertEqual(voice.listen(), "")

    def test_settings_drive_microphone_configuration(self):
        settings = Mock()
        settings.get.side_effect = lambda key, default=None: {
            "whisper_model": "small", "mic_energy": 220, "mic_extended_listening": False,
        }.get(key, default)
        config = VoiceConfig.from_settings(settings)
        self.assertEqual(config.model, "small")
        self.assertEqual(config.energy, 220)
        self.assertFalse(config.extended_listening)

    def test_changing_settings_rebuilds_the_microphone(self):
        voice = VoiceInput(VoiceConfig(energy=180))
        first = voice._signature()
        voice.config = VoiceConfig(energy=300)
        self.assertNotEqual(first, voice._signature())


if __name__ == "__main__":
    unittest.main()

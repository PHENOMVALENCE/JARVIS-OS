import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from jarvis_os.assistant import AssistantController, ConversationStore
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

    def test_web_research_synthesizes_source_grounded_answer(self):
        self.executor.execute.return_value = ActionResult(
            True, "Found web sources.", {"matches": ["SOURCE: Example\nURL: https://example.com\nSUMMARY: Current facts"]}
        )
        reply = self.controller.process("Research current battery technology")
        self.assertEqual(reply.text, "Hello there.")
        self.assertIn("https://example.com", self.provider.reply.call_args.args[0][1]["content"])


if __name__ == "__main__":
    unittest.main()

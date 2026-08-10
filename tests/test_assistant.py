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


if __name__ == "__main__":
    unittest.main()

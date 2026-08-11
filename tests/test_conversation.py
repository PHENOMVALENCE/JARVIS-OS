import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from jarvis_os.assistant import AssistantController, ConversationStore
from jarvis_os.commands import ActionResult
from jarvis_os.router import CommandRouter, split_commands
from jarvis_os.speech import HandsFreeListener


class ChainSplittingTests(unittest.TestCase):
    def test_splits_an_explicit_chain(self):
        self.assertEqual(
            split_commands("open Notepad and then type hello"),
            ["open Notepad", "type hello"],
        )

    def test_splits_before_a_command_word(self):
        self.assertEqual(
            split_commands("open Notepad and close Spotify"),
            ["open Notepad", "close Spotify"],
        )

    def test_keeps_ordinary_conjunctions_together(self):
        for text in ("search for cats and dogs", "what is bread and butter pudding",
                     "find the sales and marketing plan"):
            self.assertEqual(split_commands(text), [text], text)

    def test_handles_empty_input(self):
        self.assertEqual(split_commands("   "), [])


class FollowUpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ConversationStore(Path(self.temp.name) / "conversation.db")
        self.executor = Mock()
        self.executor.execute.return_value = ActionResult(True, "Done.")
        self.provider = Mock()
        self.provider.reply.return_value = "Sure."
        self.controller = AssistantController(self.executor, self.store, self.provider)

    def tearDown(self):
        self.temp.cleanup()

    def _last_command(self):
        return self.executor.execute.call_args.args[0]

    def test_what_about_carries_the_previous_command_forward(self):
        self.controller.process("What is the weather in London")
        self.controller.process("What about Berlin")
        command = self._last_command()
        self.assertEqual(command.action, "weather")
        self.assertEqual(command.arguments["place"], "berlin")

    def test_do_that_again_repeats_the_previous_command(self):
        self.controller.process("Take a screenshot")
        self.controller.process("Do that again")
        self.assertEqual(self._last_command().action, "screenshot")

    def test_repeat_without_history_does_not_crash(self):
        reply = self.controller.process("Do that again")
        self.executor.execute.assert_not_called()
        self.assertIn("nothing to repeat", reply.text.lower())

    def test_follow_up_without_history_falls_back_to_conversation(self):
        self.controller.process("What about Berlin")
        self.executor.execute.assert_not_called()
        self.provider.reply.assert_called_once()

    def test_chat_does_not_become_the_repeatable_command(self):
        self.controller.process("Take a screenshot")
        self.controller.process("Tell me a joke")
        self.controller.process("Do that again")
        self.assertEqual(self._last_command().action, "screenshot")

    def test_runs_each_step_of_a_chained_request(self):
        self.controller.process("Open Notepad and then take a screenshot")
        actions = [call.args[0].action for call in self.executor.execute.call_args_list]
        self.assertEqual(actions, ["open_app", "screenshot"])


class UndoRoutingTests(unittest.TestCase):
    def test_routes_undo_phrasings(self):
        router = CommandRouter()
        for text in ("Undo that", "undo", "put it back", "Restore that"):
            self.assertEqual(router.route(text).action, "undo_delete", text)


class BargeInTests(unittest.TestCase):
    def test_does_not_interrupt_by_default(self):
        speaking = threading.Event()
        speaking.set()
        listen = Mock(return_value="stop talking")
        listener = HandsFreeListener(listen, Mock(), lambda _s: None, speaking)
        listener.start()
        time.sleep(0.25)
        listener.stop()
        listen.assert_not_called()

    def test_barge_in_silences_speech_and_submits_the_new_request(self):
        speaking = threading.Event()
        speaking.set()
        received, interrupted = [], []
        listener = HandsFreeListener(
            lambda: "stop talking", received.append, lambda _s: None, speaking,
            barge_in=True, on_interrupt=lambda: interrupted.append(True),
        )
        listener.start()
        deadline = time.time() + 1
        while not received and time.time() < deadline:
            time.sleep(0.01)
        listener.stop()
        self.assertEqual(received[0], "stop talking")
        self.assertTrue(interrupted)


if __name__ == "__main__":
    unittest.main()

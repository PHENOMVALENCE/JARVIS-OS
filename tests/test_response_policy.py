import unittest
from unittest.mock import Mock

from jarvis_os.response_policy import Delivery, ResponsePolicy


def policy(terse=True, speaks=True):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "terse_responses": terse, "speak_responses": speaks,
    }.get(key, default)
    return ResponsePolicy(settings)


class VisibleActionTests(unittest.TestCase):
    """If you can see it worked, saying so is noise."""

    def test_a_spoken_request_gets_a_tone_not_a_sentence(self):
        response = policy().for_action("open_app", True, "Opened notepad.", spoken_request=True)
        self.assertIs(response.delivery, Delivery.EARCON)
        self.assertFalse(response.speaks)
        self.assertEqual(response.earcon, "done")

    def test_a_typed_request_gets_a_written_line_and_no_speech(self):
        response = policy().for_action("open_app", True, "Opened notepad.", spoken_request=False)
        self.assertIs(response.delivery, Delivery.BRIEF)
        self.assertFalse(response.speaks)
        self.assertTrue(response.shows)

    def test_window_actions_are_treated_the_same_way(self):
        for action in ("close_window", "focus_window", "context_window_state", "screenshot"):
            response = policy().for_action(action, True, "Done.", spoken_request=True)
            self.assertFalse(response.speaks, action)


class InformationalTests(unittest.TestCase):
    """Answers only exist in what is said, so they are always delivered."""

    def test_answers_are_spoken_in_full(self):
        for action in ("current_time", "weather", "web_research", "battery", "read_screen"):
            response = policy().for_action(action, True, "The answer.", spoken_request=True)
            self.assertIs(response.delivery, Delivery.FULL, action)
            self.assertTrue(response.speaks, action)

    def test_answers_are_still_shown_when_speech_is_off(self):
        response = policy(speaks=False).for_action("weather", True, "24 degrees.", True)
        self.assertFalse(response.speaks)
        self.assertTrue(response.shows)


class FailureTests(unittest.TestCase):
    """A silent failure is the worst outcome, so failures are never quiet."""

    def test_a_failure_is_always_surfaced(self):
        response = policy().for_action("open_app", False, "I could not find that app.", True)
        self.assertTrue(response.shows)
        self.assertEqual(response.earcon, "error")

    def test_a_failure_is_never_only_a_tone(self):
        for action in ("open_app", "close_window", "screenshot"):
            response = policy().for_action(action, False, "It failed.", spoken_request=True)
            self.assertIsNot(response.delivery, Delivery.EARCON, action)
            self.assertIsNot(response.delivery, Delivery.SILENT, action)

    def test_a_failure_carries_the_reason(self):
        response = policy().for_action("delete_path", False, "Path not found: notes.txt", True)
        self.assertIn("notes.txt", response.text)


class PreferenceTests(unittest.TestCase):
    def test_turning_terseness_off_restores_full_narration(self):
        response = policy(terse=False).for_action("open_app", True, "Opened notepad.", True)
        self.assertIs(response.delivery, Delivery.FULL)
        self.assertTrue(response.speaks)

    def test_conversation_is_always_delivered(self):
        self.assertTrue(policy().for_conversation().speaks)

    def test_unknown_actions_are_reported_rather_than_swallowed(self):
        response = policy().for_action("some_plugin_action", True, "Did the thing.", True)
        self.assertTrue(response.shows)

    def test_defaults_apply_without_a_settings_repository(self):
        response = ResponsePolicy().for_action("open_app", True, "Opened.", spoken_request=True)
        self.assertIs(response.delivery, Delivery.EARCON)


if __name__ == "__main__":
    unittest.main()

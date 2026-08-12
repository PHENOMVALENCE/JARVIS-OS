import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

from jarvis_os.reminders import (
    ReminderService,
    ReminderStore,
    describe_delay,
    extract_message,
    parse_clock_time,
    parse_delay,
)
from jarvis_os.router import CommandRouter
from jarvis_os.storage import Database

NOW = datetime(2026, 8, 12, 14, 30).astimezone()


class ParsingTests(unittest.TestCase):
    def test_reads_numeric_and_worded_delays(self):
        self.assertEqual(parse_delay("remind me in 10 minutes"), 600)
        self.assertEqual(parse_delay("remind me in two days"), 172800)
        self.assertEqual(parse_delay("remind me in an hour"), 3600)

    def test_reads_a_half_hour(self):
        self.assertEqual(parse_delay("remind me in half an hour to stretch"), 1800)

    def test_returns_nothing_without_a_delay(self):
        self.assertIsNone(parse_delay("remind me to buy milk"))

    def test_reads_a_clock_time(self):
        due = parse_clock_time("at 4 pm", NOW)
        self.assertEqual((due.hour, due.minute), (16, 0))

    def test_a_time_already_past_rolls_to_tomorrow(self):
        due = parse_clock_time("at 9 am", NOW)
        self.assertEqual(due.day, NOW.day + 1)

    def test_rejects_impossible_times(self):
        self.assertIsNone(parse_clock_time("at 99:99", NOW))

    def test_strips_the_scheduling_words(self):
        self.assertEqual(extract_message("remind me in 10 minutes to call mum"), "call mum")
        self.assertEqual(extract_message("set a reminder at 4 pm to join the call"), "join the call")

    def test_describes_delays_the_way_people_say_them(self):
        self.assertEqual(describe_delay(3600), "1 hour")
        self.assertEqual(describe_delay(600), "10 minutes")
        self.assertEqual(describe_delay(30), "30 seconds")
        self.assertEqual(describe_delay(172800), "2 days")


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ReminderStore(Database(Path(self.temp.name) / "jarvis.db"))
        self.notifier = Mock()
        self.spoken: list[str] = []
        self.service = ReminderService(
            self.store, self.notifier, self.spoken.append, now=lambda: NOW
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_creating_a_reminder_confirms_when_and_what(self):
        ok, message = self.service.create("remind me in 10 minutes to call mum")
        self.assertTrue(ok)
        self.assertIn("10 minutes", message)
        self.assertIn("call mum", message)

    def test_a_reminder_without_a_time_is_refused_helpfully(self):
        ok, message = self.service.create("remind me to buy milk")
        self.assertFalse(ok)
        self.assertIn("when", message.lower())

    def test_nothing_fires_before_it_is_due(self):
        self.service.create("remind me in 10 minutes to call mum")
        self.assertEqual(self.service.deliver_due(), [])
        self.notifier.send.assert_not_called()

    def test_it_fires_once_it_is_due(self):
        self.service.create("remind me in 10 minutes to call mum")
        self.service.now = lambda: NOW + timedelta(minutes=11)
        self.assertEqual(self.service.deliver_due(), ["call mum"])
        self.notifier.send.assert_called_once()
        self.assertIn("call mum", self.spoken[0])

    def test_a_delivered_reminder_does_not_repeat(self):
        self.service.create("remind me in 1 minute to stand up")
        self.service.now = lambda: NOW + timedelta(minutes=5)
        self.service.deliver_due()
        self.assertEqual(self.service.deliver_due(), [])

    def test_reminders_survive_a_restart(self):
        self.service.create("remind me in 10 minutes to call mum")
        reopened = ReminderStore(Database(Path(self.temp.name) / "jarvis.db"))
        self.assertEqual(len(reopened.pending()), 1)

    def test_a_broken_notifier_still_marks_it_delivered(self):
        self.notifier.send.side_effect = OSError("no notification service")
        self.service.create("remind me in 1 minute to stand up")
        self.service.now = lambda: NOW + timedelta(minutes=5)
        self.service.deliver_due()
        self.assertEqual(self.store.pending(), [])

    def test_clearing_removes_everything_pending(self):
        self.service.create("remind me in 10 minutes to call mum")
        self.service.create("remind me in 20 minutes to stretch")
        self.assertEqual(self.store.clear(), 2)
        self.assertEqual(self.store.pending(), [])


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def test_routes_reminder_phrasings(self):
        for text in ("Remind me in 10 minutes to call mum", "Set a timer for 5 minutes",
                     "Set a reminder at 4 pm"):
            self.assertEqual(self.router.route(text).action, "add_reminder", text)

    def test_routes_listing_and_clearing(self):
        self.assertEqual(self.router.route("What reminders do I have").action, "list_reminders")
        self.assertEqual(self.router.route("My reminders").action, "list_reminders")
        self.assertEqual(self.router.route("Cancel all reminders").action, "clear_reminders")

    def test_ordinary_requests_are_unaffected(self):
        self.assertEqual(self.router.route("What is the weather").action, "weather")
        self.assertEqual(self.router.route("Open Notepad").action, "open_app")


if __name__ == "__main__":
    unittest.main()

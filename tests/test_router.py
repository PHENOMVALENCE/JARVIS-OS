import unittest

from jarvis_os.commands import Risk
from jarvis_os.router import CommandRouter, needs_live_information, strip_wake_name


class CommandRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def test_routes_web_search(self):
        command = self.router.route("Search the internet for weather tomorrow")
        self.assertEqual(command.action, "web_search")
        self.assertEqual(command.arguments["query"], "weather tomorrow")

    def test_routes_answered_web_research(self):
        command = self.router.route("Research the latest battery technology")
        self.assertEqual(command.action, "web_research")
        self.assertEqual(command.arguments["query"], "the latest battery technology")

    def test_routes_known_folder(self):
        command = self.router.route("Open my Downloads folder")
        self.assertEqual(command.action, "open_folder")
        self.assertEqual(command.arguments["path"], "Downloads")

    def test_routes_app(self):
        command = self.router.route("Launch Spotify")
        self.assertEqual(command.action, "open_app")
        self.assertEqual(command.arguments["name"], "spotify")

    def test_sensitive_commands_have_risk(self):
        self.assertEqual(self.router.route("Close Spotify").risk, Risk.MEDIUM)
        self.assertEqual(self.router.route("Delete file notes.txt").risk, Risk.HIGH)

    def test_unknown_text_becomes_chat(self):
        self.assertEqual(self.router.route("Explain quantum computing").action, "chat")

    def test_routes_advanced_desktop_actions(self):
        self.assertEqual(self.router.route("Take a screenshot").action, "screenshot")
        self.assertEqual(self.router.route("Switch to Notepad").action, "focus_window")
        self.assertEqual(self.router.route("Start work mode").action, "work_mode")
        self.assertEqual(self.router.route("Type hello world").risk, Risk.MEDIUM)

    def test_routes_structured_ui_automation(self):
        self.assertEqual(self.router.route("Read the Notepad window").action, "inspect_ui")
        click = self.router.route("Click Save in Notepad")
        self.assertEqual(click.action, "invoke_ui")
        self.assertEqual(click.risk, Risk.MEDIUM)
        self.assertEqual(self.router.route("Select second result in Spotify").action, "select_ui")

    def test_screen_capture_requires_confirmation(self):
        self.assertEqual(self.router.route("Take a screenshot").risk, Risk.MEDIUM)
        self.assertEqual(self.router.route("What is on my screen").action, "analyze_screen")

    def test_strips_spoken_wake_name_before_routing(self):
        for spoken in ("Jarvis open Notepad", "Hey Jarvis, open Notepad",
                       "OK Jarvis open Notepad", "J.A.R.V.I.S. open Notepad"):
            command = self.router.route(spoken)
            self.assertEqual(command.action, "open_app", spoken)
            self.assertEqual(command.arguments["name"], "notepad", spoken)

    def test_strips_polite_lead_ins_and_trailing_politeness(self):
        self.assertEqual(self.router.route("Jarvis, please close Spotify").action, "close_app")
        self.assertEqual(self.router.route("Please can you open Notepad").action, "open_app")
        self.assertEqual(self.router.route("Jarvis take a screenshot for me").action, "screenshot")

    def test_wake_name_alone_is_not_swallowed(self):
        self.assertEqual(strip_wake_name("Jarvis"), "Jarvis")

    def test_routes_conversational_web_research(self):
        for spoken, expected in (
            ("Jarvis search online what is the meaning of AI", "what is the meaning of ai"),
            ("Search online for the meaning of AI", "the meaning of ai"),
            ("Look up the weather in Dar es Salaam", "the weather in dar es salaam"),
            ("Can you find out who won the election", "who won the election"),
            ("Find out about quantum computing", "quantum computing"),
        ):
            command = self.router.route(spoken)
            self.assertEqual(command.action, "web_research", spoken)
            self.assertEqual(command.arguments["query"], expected, spoken)

    def test_browser_results_stay_separate_from_spoken_research(self):
        self.assertEqual(self.router.route("Show me the results for python tutorials").action, "web_search")
        self.assertEqual(self.router.route("Browse for python tutorials").action, "web_search")

    def test_detects_questions_that_need_live_sources(self):
        for question in ("What is the weather today", "Whats the news",
                         "Who won the match last night", "Is the new Dune movie out yet",
                         "Who is the current president of Tanzania",
                         "What is the exchange rate for the dollar"):
            self.assertTrue(needs_live_information(question), question)

    def test_leaves_timeless_questions_to_the_model(self):
        for question in ("What is the meaning of AI", "Explain quantum computing",
                         "What is the capital of France", "Why is the sky blue",
                         "Who was Isaac Newton", "How are you",
                         "I am currently working on a project"):
            self.assertFalse(needs_live_information(question), question)

    def test_package_management_is_high_risk(self):
        command = self.router.route("Install package VideoLAN.VLC")
        self.assertEqual(command.action, "install_package")
        self.assertEqual(command.risk, Risk.HIGH)


if __name__ == "__main__":
    unittest.main()

import unittest

from jarvis_os.commands import Risk
from jarvis_os.router import CommandRouter


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

    def test_package_management_is_high_risk(self):
        command = self.router.route("Install package VideoLAN.VLC")
        self.assertEqual(command.action, "install_package")
        self.assertEqual(command.risk, Risk.HIGH)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path
from unittest.mock import Mock

from jarvis_os.context import ContextEngine, PowerInfo, WindowInfo
from jarvis_os.router import CommandRouter


def window(title="", process="", handle=1, minimized=False):
    return WindowInfo(handle=handle, title=title, process=process, process_id=handle * 10,
                      minimized=minimized)


class FakeObserver:
    def __init__(self, foreground=None, windows=(), power=None, online=True):
        self._foreground = foreground or WindowInfo()
        self._windows = tuple(windows)
        self._power = power or PowerInfo()
        self._online = online
        self.observations = 0

    def foreground(self):
        self.observations += 1
        return self._foreground

    def visible_windows(self, limit=40):
        return self._windows

    def power(self):
        return self._power

    def online(self):
        return self._online


def engine(observer, privacy=False, clock=None):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: (
        privacy if key == "privacy_mode" else default
    )
    context = ContextEngine(settings, observer, clock or (lambda: 1000.0))
    context._clipboard_kind = lambda: "text"
    return context


class SnapshotTests(unittest.TestCase):
    def test_reports_the_foreground_window(self):
        context = engine(FakeObserver(window("Budget.xlsx - Excel", "EXCEL.EXE")))
        self.assertEqual(context.snapshot().foreground.process, "EXCEL.EXE")

    def test_repeated_reads_come_from_the_cache(self):
        observer = FakeObserver(window("Notepad", "notepad.exe"))
        context = engine(observer)
        for _ in range(10):
            context.snapshot()
        self.assertEqual(observer.observations, 1)

    def test_the_cache_expires(self):
        observer = FakeObserver(window("Notepad", "notepad.exe"))
        now = [1000.0]
        context = engine(observer, clock=lambda: now[0])
        context.snapshot()
        now[0] += 10
        context.snapshot()
        self.assertEqual(observer.observations, 2)

    def test_refresh_forces_a_new_observation(self):
        observer = FakeObserver(window("Notepad", "notepad.exe"))
        context = engine(observer)
        context.snapshot()
        context.snapshot(refresh=True)
        self.assertEqual(observer.observations, 2)

    def test_an_observer_failure_degrades_rather_than_raising(self):
        observer = FakeObserver()
        observer.foreground = Mock(side_effect=OSError("no desktop"))
        snapshot = engine(observer).snapshot()
        self.assertFalse(snapshot.foreground.present)
        self.assertEqual(snapshot.windows, ())


class PrivacyTests(unittest.TestCase):
    """Window titles name documents and web pages, so privacy mode withholds them."""

    def setUp(self):
        self.observer = FakeObserver(
            window("Payslip March.pdf - Acrobat", "Acrobat.exe"),
            [window("Payslip March.pdf - Acrobat", "Acrobat.exe")],
        )

    def test_titles_are_withheld_in_privacy_mode(self):
        snapshot = engine(self.observer, privacy=True).snapshot()
        self.assertEqual(snapshot.foreground.title, "")
        self.assertEqual(snapshot.windows[0].title, "")

    def test_the_process_is_still_available(self):
        snapshot = engine(self.observer, privacy=True).snapshot()
        self.assertEqual(snapshot.foreground.process, "Acrobat.exe")

    def test_clipboard_shape_is_withheld_too(self):
        self.assertEqual(engine(self.observer, privacy=True).snapshot().clipboard_kind, "hidden")

    def test_describe_says_so_rather_than_leaking(self):
        self.assertIn("Privacy mode", engine(self.observer, privacy=True).describe())


class ResolutionTests(unittest.TestCase):
    def test_this_means_the_foreground_window(self):
        context = engine(FakeObserver(window("Cursor", "Cursor.exe"), [window("Cursor", "Cursor.exe")]))
        self.assertEqual(context.resolve_window().process, "Cursor.exe")

    def test_a_named_window_wins_over_the_foreground(self):
        context = engine(FakeObserver(
            window("Cursor", "Cursor.exe", 1),
            [window("Cursor", "Cursor.exe", 1), window("Spotify", "Spotify.exe", 2)],
        ))
        self.assertEqual(context.resolve_window("spotify").process, "Spotify.exe")

    def test_our_own_window_is_never_the_answer(self):
        """Saying "close this" while looking at J.A.R.V.I.S means what is behind it."""
        context = engine(FakeObserver(
            window("J.A.R.V.I.S", "python.exe", 1),
            [window("J.A.R.V.I.S", "python.exe", 1), window("Notepad", "notepad.exe", 2)],
        ))
        self.assertEqual(context.resolve_window().process, "notepad.exe")

    def test_nothing_to_resolve_returns_nothing(self):
        self.assertIsNone(engine(FakeObserver()).resolve_window())

    def test_the_containing_folder_comes_from_the_last_file(self):
        context = engine(FakeObserver())
        context.note_target(file=Path(__file__))
        self.assertEqual(context.resolve_folder(), Path(__file__).parent)

    def test_no_recent_file_means_no_folder(self):
        self.assertIsNone(engine(FakeObserver()).resolve_folder())


class MemoryTests(unittest.TestCase):
    def test_a_failure_is_remembered_for_recall(self):
        context = engine(FakeObserver())
        context.note_action("delete_path", False, "Path not found: notes.txt")
        self.assertIn("notes.txt", context.referents.failure)

    def test_the_last_action_is_remembered(self):
        context = engine(FakeObserver())
        context.note_action("screenshot", True, "Saved.")
        self.assertEqual(context.referents.action, "screenshot")


class HealthTests(unittest.TestCase):
    def test_reports_ok_with_windows_present(self):
        context = engine(FakeObserver(window("Notepad", "notepad.exe"), [window("Notepad", "notepad.exe")]))
        self.assertEqual(context.health()["status"], "OK")

    def test_reports_degraded_with_nothing_visible(self):
        self.assertEqual(engine(FakeObserver()).health()["status"], "DEGRADED")

    def test_reports_failed_when_observation_raises(self):
        context = engine(FakeObserver())
        context.snapshot = Mock(side_effect=OSError("broken"))
        self.assertEqual(context.health()["status"], "FAILED")


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def test_context_phrasings_route_without_the_model(self):
        for text, action in (
            ("Close this", "close_window"),
            ("Close that window", "close_window"),
            ("Minimise this", "context_window_state"),
            ("Maximize that", "context_window_state"),
            ("What am I doing", "describe_context"),
            ("Open the folder this file is in", "open_containing_folder"),
        ):
            self.assertEqual(self.router.route(text).action, action, text)

    def test_closing_this_still_asks_first(self):
        self.assertEqual(self.router.route("Close this").risk.value, "medium")

    def test_naming_a_window_keeps_the_existing_route(self):
        self.assertEqual(self.router.route("Close Spotify").action, "close_app")
        self.assertEqual(self.router.route("Minimize Notepad").action, "window_state")


if __name__ == "__main__":
    unittest.main()

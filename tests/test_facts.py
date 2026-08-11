import unittest
from datetime import datetime
from unittest.mock import Mock

from jarvis_os.facts import FactService, calculate, convert
from jarvis_os.router import CommandRouter


class CalculateTests(unittest.TestCase):
    def test_evaluates_arithmetic(self):
        self.assertEqual(calculate("2+2"), "4")
        self.assertEqual(calculate("12 * 8 + 4"), "100")
        self.assertEqual(calculate("10 / 4"), "2.5")

    def test_understands_spoken_operators(self):
        self.assertEqual(calculate("7 plus 5"), "12")
        self.assertEqual(calculate("9 times 3"), "27")
        self.assertEqual(calculate("100 divided by 8"), "12.5")

    def test_handles_percentages(self):
        self.assertEqual(calculate("15 percent of 240"), "36")

    def test_rejects_text_that_is_not_maths(self):
        for value in ("what is the capital of France", "open notepad", "42", "hello", ""):
            self.assertIsNone(calculate(value), value)

    def test_refuses_to_execute_code(self):
        for value in ("__import__('os').system('dir')", "open('x').read()", "1 if x else 2"):
            self.assertIsNone(calculate(value), value)

    def test_survives_division_by_zero(self):
        self.assertIsNone(calculate("5 / 0"))


class ConvertTests(unittest.TestCase):
    def test_converts_length_and_mass(self):
        self.assertEqual(convert(10, "km", "miles"), "6.2137")
        self.assertEqual(convert(1, "m", "cm"), "100")
        self.assertEqual(convert(1, "kg", "lb"), "2.2046")

    def test_converts_temperature(self):
        self.assertEqual(convert(100, "c", "f"), "212")
        self.assertEqual(convert(32, "f", "c"), "0")
        self.assertEqual(convert(0, "c", "k"), "273.15")

    def test_refuses_mismatched_dimensions(self):
        self.assertIsNone(convert(1, "kg", "miles"))
        self.assertIsNone(convert(1, "banana", "m"))


class FactServiceTests(unittest.TestCase):
    def setUp(self):
        self.facts = FactService(now=lambda: datetime(2026, 8, 11, 20, 5))

    def test_reports_time_and_date(self):
        self.assertEqual(self.facts.current_time({}).message, "It's 8:05 PM.")
        self.assertEqual(self.facts.current_date({}).message, "It's Tuesday, August 11, 2026.")

    def test_speaks_unit_names_in_full(self):
        result = self.facts.convert({"value": 100, "source": "f", "target": "c"})
        self.assertEqual(result.message, "100 degrees Fahrenheit is 37.7778 degrees Celsius.")

    def test_reports_a_failed_calculation_without_crashing(self):
        result = self.facts.calculate({"expression": "nonsense"})
        self.assertFalse(result.success)


class FactRoutingTests(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def test_routes_instant_questions_away_from_the_model(self):
        for text, action in (
            ("What time is it", "current_time"),
            ("Jarvis what is the date", "current_date"),
            ("What day is it today", "current_date"),
            ("What is 15 percent of 240", "calculate"),
            ("Calculate 12 * 8 + 4", "calculate"),
            ("Convert 10 km to miles", "convert"),
            ("5 kg in pounds", "convert"),
            ("How is my battery", "battery"),
            ("How much disk space do I have", "disk_space"),
        ):
            self.assertEqual(self.router.route(text).action, action, text)

    def test_leaves_real_questions_to_the_model(self):
        for text in ("What is the capital of France", "What is the meaning of AI",
                     "Explain quantum computing", "What is a black hole"):
            self.assertEqual(self.router.route(text).action, "chat", text)

    def test_does_not_hijack_commands_that_look_numeric(self):
        self.assertEqual(self.router.route("Volume 40").action, "set_volume")
        self.assertEqual(self.router.route("Open Notepad").action, "open_app")


if __name__ == "__main__":
    unittest.main()

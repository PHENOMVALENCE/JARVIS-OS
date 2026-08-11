"""Instant answers that never touch the language model.

Routing "what time is it" through a local model costs seconds and can still
get it wrong. These questions have exact answers the computer already knows,
so answer them directly and spend the model on things that need judgement.
"""

from __future__ import annotations

import ast
import ctypes
import operator
import re
import shutil
from datetime import datetime
from pathlib import Path

from .commands import ActionResult


_UNITS = {
    # length (metres)
    "mm": ("length", 0.001), "millimetre": ("length", 0.001), "millimeter": ("length", 0.001),
    "cm": ("length", 0.01), "centimetre": ("length", 0.01), "centimeter": ("length", 0.01),
    "m": ("length", 1.0), "metre": ("length", 1.0), "meter": ("length", 1.0),
    "km": ("length", 1000.0), "kilometre": ("length", 1000.0), "kilometer": ("length", 1000.0),
    "in": ("length", 0.0254), "inch": ("length", 0.0254), "inches": ("length", 0.0254),
    "ft": ("length", 0.3048), "foot": ("length", 0.3048), "feet": ("length", 0.3048),
    "yd": ("length", 0.9144), "yard": ("length", 0.9144),
    "mi": ("length", 1609.344), "mile": ("length", 1609.344), "miles": ("length", 1609.344),
    # mass (grams)
    "mg": ("mass", 0.001), "g": ("mass", 1.0), "gram": ("mass", 1.0),
    "kg": ("mass", 1000.0), "kilogram": ("mass", 1000.0), "kilo": ("mass", 1000.0),
    "oz": ("mass", 28.349523125), "ounce": ("mass", 28.349523125),
    "lb": ("mass", 453.59237), "lbs": ("mass", 453.59237), "pound": ("mass", 453.59237),
    # volume (litres)
    "ml": ("volume", 0.001), "l": ("volume", 1.0), "litre": ("volume", 1.0), "liter": ("volume", 1.0),
    "gal": ("volume", 3.785411784), "gallon": ("volume", 3.785411784),
    "pint": ("volume", 0.473176473), "cup": ("volume", 0.2365882365),
}

_TEMPERATURES = {"c", "celsius", "centigrade", "f", "fahrenheit", "k", "kelvin"}

# Abbreviations read badly aloud: "100 f is 37 c" should be spoken in full.
_SPOKEN_UNITS = {
    "c": "degrees Celsius", "celsius": "degrees Celsius", "centigrade": "degrees Celsius",
    "f": "degrees Fahrenheit", "fahrenheit": "degrees Fahrenheit",
    "k": "kelvin", "kelvin": "kelvin",
    "mm": "millimetres", "cm": "centimetres", "m": "metres", "km": "kilometres",
    "in": "inches", "ft": "feet", "yd": "yards", "mi": "miles",
    "mg": "milligrams", "g": "grams", "kg": "kilograms",
    "oz": "ounces", "lb": "pounds", "lbs": "pounds",
    "ml": "millilitres", "l": "litres", "gal": "gallons",
}


def spoken_unit(unit: str) -> str:
    return _SPOKEN_UNITS.get(unit.lower(), unit)


_SAFE_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}

_WORD_OPERATORS = (
    (r"\bplus\b|\badded to\b", "+"), (r"\bminus\b|\bsubtract\b", "-"),
    (r"\btimes\b|\bmultiplied by\b", "*"), (r"\bdivided by\b|\bover\b", "/"),
    (r"\bto the power of\b|\bsquared\b", "**"), (r"\bpercent of\b", "% of"),
)


def _round(value: float) -> str:
    """Trim trailing zeros so spoken numbers do not read as '5.000000'."""
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{round(value, 4):g}"


def _evaluate(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPERATORS:
        return _SAFE_OPERATORS[type(node.op)](_evaluate(node.left), _evaluate(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPERATORS:
        return _SAFE_OPERATORS[type(node.op)](_evaluate(node.operand))
    raise ValueError("unsupported expression")


def calculate(expression: str) -> str | None:
    """Evaluate arithmetic without exec/eval, returning None when it is not maths."""
    text = expression.lower().strip(" ?.!")
    for pattern, symbol in _WORD_OPERATORS:
        text = re.sub(pattern, symbol, text)
    percent = re.fullmatch(r"\s*([\d.]+)\s*%\s*of\s*([\d.]+)\s*", text)
    if percent:
        return _round(float(percent.group(1)) / 100 * float(percent.group(2)))
    text = text.replace("x", "*").replace("^", "**").replace(",", "")
    if not re.fullmatch(r"[\d\s+\-*/%().]+", text) or not re.search(r"\d", text):
        return None
    if not re.search(r"[+\-*/%]", text):
        return None
    try:
        return _round(_evaluate(ast.parse(text, mode="eval").body))
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError, OverflowError):
        return None


def _to_celsius(value: float, unit: str) -> float:
    if unit.startswith("f"):
        return (value - 32) * 5 / 9
    return value - 273.15 if unit.startswith("k") else value


def _from_celsius(value: float, unit: str) -> float:
    if unit.startswith("f"):
        return value * 9 / 5 + 32
    return value + 273.15 if unit.startswith("k") else value


def convert(value: float, source: str, target: str) -> str | None:
    source, target = source.lower().rstrip("s"), target.lower().rstrip("s")
    if source in _TEMPERATURES and target in _TEMPERATURES:
        return _round(_from_celsius(_to_celsius(value, source), target))
    origin, destination = _UNITS.get(source), _UNITS.get(target)
    if not origin or not destination or origin[0] != destination[0]:
        return None
    return _round(value * origin[1] / destination[1])


class FactService:
    """Answers the computer can give exactly, with no model involved."""

    def __init__(self, home: Path | None = None, now=datetime.now):
        self.home = home or Path.home()
        self.now = now

    def current_time(self, _args: dict) -> ActionResult:
        return ActionResult(True, f"It's {self.now():%I:%M %p}.".replace(" 0", " "))

    def current_date(self, _args: dict) -> ActionResult:
        return ActionResult(True, f"It's {self.now():%A, %B %d, %Y}.".replace(" 0", " "))

    def calculate(self, args: dict) -> ActionResult:
        expression = str(args["expression"])
        answer = calculate(expression)
        if answer is None:
            return ActionResult(False, f"I could not work out {expression}.")
        return ActionResult(True, f"That's {answer}.")

    def convert(self, args: dict) -> ActionResult:
        value, source, target = float(args["value"]), str(args["source"]), str(args["target"])
        answer = convert(value, source, target)
        if answer is None:
            return ActionResult(False, f"I cannot convert {spoken_unit(source)} to {spoken_unit(target)}.")
        return ActionResult(
            True, f"{_round(value)} {spoken_unit(source)} is {answer} {spoken_unit(target)}."
        )

    def battery(self, _args: dict) -> ActionResult:
        class _Status(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong),
            ]

        status = _Status()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return ActionResult(False, "I could not read the battery status.")
        if status.BatteryFlag == 128:
            return ActionResult(True, "This machine has no battery; it runs on mains power.")
        plugged = status.ACLineStatus == 1
        percent = status.BatteryLifePercent
        if plugged:
            return ActionResult(True, f"Battery is at {percent} percent and charging.")
        remaining = status.BatteryLifeTime
        if remaining and remaining != 0xFFFFFFFF:
            hours, minutes = divmod(remaining // 60, 60)
            return ActionResult(True, f"Battery is at {percent} percent, about {hours} hours {minutes} minutes left.")
        return ActionResult(True, f"Battery is at {percent} percent on battery power.")

    def disk_space(self, _args: dict) -> ActionResult:
        usage = shutil.disk_usage(self.home.anchor or str(self.home))
        free = usage.free / 1e9
        return ActionResult(
            True,
            f"{free:.0f} GB free of {usage.total / 1e9:.0f} GB, about {usage.free / usage.total * 100:.0f} percent.",
        )

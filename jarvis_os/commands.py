"""Typed command contracts shared by the router, UI, and action executor."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Risk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class Command:
    action: str
    arguments: dict[str, Any] = field(default_factory=dict)
    risk: Risk = Risk.LOW
    raw_text: str = ""


@dataclass(frozen=True)
class ActionResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)

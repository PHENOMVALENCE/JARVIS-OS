"""Structured Windows UI Automation using accessible control properties."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .commands import ActionResult


@dataclass(frozen=True)
class ElementSummary:
    name: str
    control_type: str
    automation_id: str
    enabled: bool


class UIAutomationService:
    def __init__(self, backend: str = "uia"):
        self.backend = backend

    def _window(self, title: str):
        from pywinauto import Desktop
        windows = Desktop(backend=self.backend).windows(title_re=f".*{self._escape(title)}.*", visible_only=True)
        if not windows:
            raise LookupError(f"No visible window matched {title}.")
        return windows[0]

    @staticmethod
    def _escape(value: str) -> str:
        import re
        return re.escape(value)

    def inspect(self, title: str, limit: int = 100) -> list[ElementSummary]:
        window = self._window(title)
        elements = []
        for control in window.descendants()[:limit]:
            info = control.element_info
            name = str(info.name or "").strip()
            if name:
                elements.append(ElementSummary(name, str(info.control_type), str(info.automation_id or ""), control.is_enabled()))
        return elements

    def read(self, title: str) -> ActionResult:
        elements = self.inspect(title)
        lines = [f"{item.control_type}: {item.name}" for item in elements]
        if not lines:
            return ActionResult(False, f"No accessible text was exposed by {title}.")
        return ActionResult(True, f"Accessible contents of {title}:", {"matches": lines})

    def invoke(self, title: str, control_name: str) -> ActionResult:
        window = self._window(title)
        control = window.child_window(title_re=f".*{self._escape(control_name)}.*")
        wrapper = control.wrapper_object()
        if not wrapper.is_enabled():
            return ActionResult(False, f"{control_name} is disabled.")
        if hasattr(wrapper, "invoke"):
            wrapper.invoke()
        else:
            wrapper.click_input()
        return ActionResult(True, f"Activated {control_name} in {title}.")

    def set_text(self, title: str, control_name: str, text: str) -> ActionResult:
        window = self._window(title)
        wrapper = window.child_window(title_re=f".*{self._escape(control_name)}.*").wrapper_object()
        if getattr(wrapper.element_info, "control_type", "") in {"Password", "PasswordBox"}:
            return ActionResult(False, "Password fields cannot be filled by automation.")
        if hasattr(wrapper, "set_edit_text"):
            wrapper.set_edit_text(text)
        else:
            wrapper.set_focus()
            wrapper.type_keys(text, with_spaces=True, set_foreground=True)
        return ActionResult(True, f"Entered text in {control_name}.")

    def select(self, title: str, item_name: str) -> ActionResult:
        window = self._window(title)
        wrapper = window.child_window(title_re=f".*{self._escape(item_name)}.*").wrapper_object()
        if hasattr(wrapper, "select"):
            wrapper.select()
        else:
            wrapper.click_input()
        return ActionResult(True, f"Selected {item_name} in {title}.")

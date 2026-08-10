"""Manifest-driven plugin discovery with failure isolation."""

from __future__ import annotations

import importlib.util
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .commands import ActionResult, Command, Risk
from .storage import Database


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    actions: dict[str, Risk]
    network: bool = False


@dataclass
class LoadedPlugin:
    manifest: PluginManifest
    instance: Any | None
    enabled: bool
    error: str = ""


class PluginManager:
    def __init__(self, directory: Path, database: Database, core_actions, data_dir: Path):
        self.directory = directory
        self.database = database
        self.core_actions = core_actions
        self.data_dir = data_dir
        self.plugins: dict[str, LoadedPlugin] = {}
        self.action_plugins: dict[str, LoadedPlugin] = {}
        self.discover()

    def discover(self) -> None:
        self.plugins.clear()
        self.action_plugins.clear()
        if not self.directory.is_dir():
            return
        for manifest_path in sorted(self.directory.glob("*/manifest.json")):
            try:
                raw = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = PluginManifest(
                    plugin_id=raw["id"], name=raw["name"], version=raw["version"],
                    actions={name: Risk(risk) for name, risk in raw.get("actions", {}).items()},
                    network=bool(raw.get("network", False)),
                )
                enabled = self._enabled(manifest.plugin_id)
                instance = self._load(manifest_path.parent, manifest) if enabled else None
                loaded = LoadedPlugin(manifest, instance, enabled)
            except Exception as exc:
                plugin_id = manifest_path.parent.name
                fallback = PluginManifest(plugin_id, plugin_id, "invalid", {})
                loaded = LoadedPlugin(fallback, None, False, str(exc))
            self.plugins[loaded.manifest.plugin_id] = loaded
            if loaded.enabled and loaded.instance:
                for action in loaded.manifest.actions:
                    self.action_plugins[action] = loaded

    def _enabled(self, plugin_id: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute("SELECT enabled FROM plugins WHERE plugin_id = ?", (plugin_id,)).fetchone()
            if row is None:
                connection.execute("INSERT INTO plugins(plugin_id, enabled) VALUES(?, 1)", (plugin_id,))
                return True
            return bool(row["enabled"])

    def _load(self, directory: Path, manifest: PluginManifest):
        module_path = directory / "plugin.py"
        if not module_path.is_file():
            raise ValueError("plugin.py is missing")
        spec = importlib.util.spec_from_file_location(f"jarvis_plugin_{manifest.plugin_id}", module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load {manifest.plugin_id}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.create_plugin({"data_dir": self.data_dir / "plugins" / manifest.plugin_id})

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO plugins(plugin_id, enabled) VALUES(?, ?) ON CONFLICT(plugin_id) DO UPDATE SET enabled=excluded.enabled",
                (plugin_id, int(enabled)),
            )
        self.discover()

    def route(self, text: str) -> Command | None:
        for loaded in self.plugins.values():
            if not loaded.enabled or not loaded.instance:
                continue
            try:
                routed = loaded.instance.route(text)
                if routed:
                    action, arguments = routed
                    risk = loaded.manifest.actions.get(action)
                    if risk is None:
                        continue
                    return Command(action, arguments, risk, text)
            except Exception as exc:
                loaded.error = str(exc)
        return None

    def execute(self, command: Command) -> ActionResult:
        loaded = self.action_plugins.get(command.action)
        if not loaded:
            return self.core_actions.execute(command)
        try:
            result = loaded.instance.execute(command.action, command.arguments)
            if not isinstance(result, ActionResult):
                raise TypeError("Plugin actions must return ActionResult")
            return result
        except Exception as exc:
            loaded.error = str(exc)
            return ActionResult(False, f"{loaded.manifest.name} plugin failed: {exc}")

    def status(self) -> list[dict[str, Any]]:
        return [
            {"id": item.manifest.plugin_id, "name": item.manifest.name, "version": item.manifest.version,
             "enabled": item.enabled, "network": item.manifest.network, "error": item.error}
            for item in self.plugins.values()
        ]

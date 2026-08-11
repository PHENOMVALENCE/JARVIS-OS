"""Conversation, voice, and command orchestration for the desktop application."""

from __future__ import annotations

import sqlite3
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .commands import Command
from .router import CommandRouter, needs_live_information
from .security import SecureExecutor
from .settings import Settings


SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S, a warm, perceptive Windows desktop assistant. Talk like a trusted, "
    "intelligent companion: natural, relaxed, direct, and never stiff or ceremonial. Use contractions "
    "and everyday wording. Match the user's tone without pretending to have feelings or experiences. "
    "The application handles local computer actions separately. Never claim an action occurred "
    "unless the system reports it. Protect the user's privacy and explain uncertainty plainly. "
    "Avoid repetitive greetings, excessive formality, emoji, and canned phrases such as 'Certainly' "
    "or 'How may I assist you today?'"
)

VOICE_RESPONSE_PROMPT = (
    "This is a live spoken conversation. Infer the user's intended request from natural speech, "
    "including harmless filler words or self-corrections. Reply in one to three conversational sentences "
    "unless they ask for detail. Use plain spoken language with no Markdown, emoji, headings, lists, or raw URLs."
)


class ChatProvider(Protocol):
    def reply(self, messages: list[dict[str, str]]) -> str: ...


class OllamaProvider:
    def __init__(self, model: str):
        self.model = model

    def reply(self, messages: list[dict[str, str]]) -> str:
        import ollama
        response = ollama.chat(model=self.model, messages=messages)
        return response["message"]["content"].strip()


class OpenAIProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def reply(self, messages: list[dict[str, str]]) -> str:
        from openai import OpenAI
        response = OpenAI(api_key=self.api_key).chat.completions.create(model="gpt-4o-mini", messages=messages)
        return (response.choices[0].message.content or "").strip()


class ConversationStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as database:
            database.execute(
                "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL)"
            )

    @contextmanager
    def _connect(self):
        database = sqlite3.connect(self.path)
        try:
            yield database
            database.commit()
        finally:
            database.close()

    def append(self, role: str, content: str) -> None:
        with self._connect() as database:
            database.execute("INSERT INTO messages(role, content) VALUES(?, ?)", (role, content))

    def recent(self, limit: int = 20) -> list[dict[str, str]]:
        with self._connect() as database:
            rows = database.execute(
                "SELECT role, content FROM (SELECT id, role, content FROM messages ORDER BY id DESC LIMIT ?) ORDER BY id",
                (limit,),
            ).fetchall()
        return [{"role": role, "content": content} for role, content in rows]

    def clear(self) -> None:
        with self._connect() as database:
            database.execute("DELETE FROM messages")


@dataclass(frozen=True)
class AssistantReply:
    text: str
    details: list[str] | None = None


class AssistantController:
    def __init__(self, executor: SecureExecutor, store: ConversationStore, provider: ChatProvider, plugins=None, workflows=None, settings_repo=None):
        self.executor = executor
        self.store = store
        self.provider = provider
        self.router = CommandRouter()
        self.plugins = plugins
        self.workflows = workflows
        self.settings_repo = settings_repo

    def _auto_web_enabled(self) -> bool:
        return not self.settings_repo or bool(self.settings_repo.get("auto_web_answers", True))

    def _upgrade_to_live_answer(self, command: Command) -> tuple[Command, bool]:
        """Send time-sensitive questions to live sources instead of stale weights."""
        if command.action != "chat" or not self._auto_web_enabled():
            return command, False
        question = str(command.arguments.get("message", "")).strip()
        if not question or not needs_live_information(question):
            return command, False
        return Command("web_research", {"query": question}, raw_text=command.raw_text), True

    def process(self, text: str, spoken: bool = False) -> AssistantReply:
        workflow = self.workflows.match_voice(text) if self.workflows else None
        if workflow:
            result = self.workflows.run(workflow)
            return AssistantReply(result.message)
        command = self.plugins.route(text) if self.plugins else None
        command = command or self.router.route(text)
        command, auto_research = self._upgrade_to_live_answer(command)
        if command.action != "chat":
            result = self.executor.execute(command)
            details = result.data.get("matches") if result.data else None
            if command.action == "semantic_search" and result.success and details:
                context = "\n\n".join(details)
                answer = self.provider.reply([
                    {"role": "system", "content": "Answer only from the supplied local document passages. Cite each source path and page used. Say when the evidence is insufficient."},
                    *([{"role": "system", "content": VOICE_RESPONSE_PROMPT}] if spoken else []),
                    {"role": "user", "content": f"Question: {command.arguments['query']}\n\nPassages:\n{context}"},
                ])
                return AssistantReply(answer, details)
            if command.action == "web_research" and result.success and details:
                context = "\n\n".join(details)
                answer = self.provider.reply([
                    {"role": "system", "content": "Answer the question using the supplied current web search results. Be clear and useful. Cite supporting URLs inline. Distinguish facts from inference and say when the snippets are insufficient."},
                    *([{"role": "system", "content": VOICE_RESPONSE_PROMPT}] if spoken else []),
                    {"role": "user", "content": f"Question: {command.arguments['query']}\n\nWeb results:\n{context}"},
                ])
                return AssistantReply(answer, details)
            if not auto_research:
                return AssistantReply(result.message, details)
            # The user asked a normal question, so answer conversationally rather
            # than reporting a search failure they never asked for.
            text = str(command.arguments["query"])
        memory_enabled = not self.settings_repo or self.settings_repo.get("conversation_memory", True)
        if memory_enabled:
            self.store.append("user", text)
        history = self.store.recent() if memory_enabled else [{"role": "user", "content": text}]
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *([{"role": "system", "content": VOICE_RESPONSE_PROMPT}] if spoken else []),
            *history,
        ]
        reply = self.provider.reply(messages)
        if memory_enabled:
            self.store.append("assistant", reply)
        return AssistantReply(reply)


class VoiceInput:
    """Lazy, push-to-talk Whisper microphone so startup remains responsive."""

    def __init__(self, model: str = "base"):
        self.model = model
        self._microphone = None
        self._lock = threading.Lock()

    NO_SPEECH = {"", "[blank_audio]", "[silence]", "(silence)", "thank you for watching"}

    def listen(self, timeout: int = 15, phrase_time_limit: int = 30) -> str:
        with self._lock:
            if self._microphone is None:
                import torch
                from whisper_mic import WhisperMic
                self._microphone = WhisperMic(
                    model=self.model, english=False, verbose=False, energy=300,
                    pause=1.25, dynamic_energy=True, save_file=False,
                    device="cuda" if torch.cuda.is_available() else "cpu",
                    implementation="whisper", hallucinate_threshold=300,
                )
            result = self._microphone.listen(timeout=timeout, phrase_time_limit=phrase_time_limit)
        return self.clean_transcript(result)

    @classmethod
    def clean_transcript(cls, result: str | None) -> str:
        value = re.sub(r"\s+", " ", str(result or "")).strip()
        if value.lower() in cls.NO_SPEECH or "timeout: no speech" in value.lower():
            return ""
        return value


def make_provider(settings: Settings, settings_repo=None) -> ChatProvider:
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when JARVIS_LLM_PROVIDER=openai.")
        return OpenAIProvider(settings.openai_api_key)
    model = settings_repo.get("ollama_model", settings.ollama_model) if settings_repo else settings.ollama_model
    return OllamaProvider(model)

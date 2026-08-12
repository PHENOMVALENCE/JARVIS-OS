"""Conversation, voice, and command orchestration for the desktop application."""

from __future__ import annotations

import sqlite3
import re
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .commands import Command
from .language import REPLY_IN_SWAHILI, SWAHILI, detect, to_command_english
from .router import FOLLOW_UP_ARGUMENT, CommandRouter, needs_live_information, split_commands
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
    """Local model access that keeps the model resident between requests.

    Loading gemma2:2b from cold costs far more than generating the answer, so
    an unloaded model is the difference between a 15 second wait and one second.
    """

    def __init__(self, model: str, keep_alive: str = "30m"):
        self.model = model
        self.keep_alive = keep_alive

    def warm(self) -> None:
        """Load the model without generating, so the first request is fast."""
        import ollama
        ollama.generate(model=self.model, prompt="", keep_alive=self.keep_alive)

    def reply(self, messages: list[dict[str, str]]) -> str:
        import ollama
        response = ollama.chat(model=self.model, messages=messages, keep_alive=self.keep_alive)
        return response["message"]["content"].strip()

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        import ollama
        stream = ollama.chat(
            model=self.model, messages=messages, stream=True, keep_alive=self.keep_alive
        )
        for part in stream:
            chunk = (part.get("message") or {}).get("content") or ""
            if chunk:
                yield chunk


class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def reply(self, messages: list[dict[str, str]]) -> str:
        from openai import OpenAI
        response = OpenAI(api_key=self.api_key).chat.completions.create(model=self.model, messages=messages)
        return (response.choices[0].message.content or "").strip()

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        from openai import OpenAI
        completion = OpenAI(api_key=self.api_key).chat.completions.create(
            model=self.model, messages=messages, stream=True
        )
        for part in completion:
            chunk = part.choices[0].delta.content or ""
            if chunk:
                yield chunk


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
        self._last_action_context: str | None = None
        self._last_command: Command | None = None
        self.last_language = "en"

    def _auto_web_enabled(self) -> bool:
        return not self.settings_repo or bool(self.settings_repo.get("auto_web_answers", True))

    def _memory_enabled(self) -> bool:
        return not self.settings_repo or bool(self.settings_repo.get("conversation_memory", True))

    def _memory_limit(self) -> int:
        if not self.settings_repo:
            return 40
        return max(10, min(80, int(self.settings_repo.get("conversation_memory_limit", 40))))

    def _conversation_context(self, limit: int = 8) -> str:
        """Recent dialogue, so screen analysis knows what the user was discussing."""
        if not self._memory_enabled():
            return ""
        history = self.store.recent(limit=limit)
        return "\n".join(f"{item['role']}: {item['content'][:240]}" for item in history)

    def _answer(self, messages: list[dict[str, str]], on_chunk: Callable[[str], None] | None) -> str:
        """Stream the reply when the caller can use it, so speech starts early."""
        stream = getattr(self.provider, "stream", None)
        if not on_chunk or not callable(stream):
            return self.provider.reply(messages)
        parts: list[str] = []
        try:
            for chunk in stream(messages):
                parts.append(chunk)
                on_chunk(chunk)
        except Exception:
            if not parts:
                return self.provider.reply(messages)
        return "".join(parts).strip()

    def _system_prompt(self) -> str:
        if not self._last_action_context:
            return SYSTEM_PROMPT
        return f"{SYSTEM_PROMPT}\n\nRecent system activity: {self._last_action_context}"

    def _resolve_follow_up(self, command: Command) -> Command | AssistantReply:
        """Turn "again" and "what about Berlin" into the command they refer to."""
        if command.action == "repeat_last":
            if not self._last_command:
                return AssistantReply("There is nothing to repeat yet.")
            return self._last_command
        if command.action != "follow_up":
            return command
        subject = str(command.arguments.get("subject", "")).strip()
        argument = FOLLOW_UP_ARGUMENT.get(self._last_command.action) if self._last_command else None
        if not self._last_command or not argument or not subject:
            # Nothing to carry over, so treat it as ordinary conversation.
            return Command("chat", {"message": command.raw_text}, raw_text=command.raw_text)
        arguments = dict(self._last_command.arguments)
        arguments[argument] = subject
        return Command(self._last_command.action, arguments, self._last_command.risk, command.raw_text)

    def _upgrade_to_live_answer(self, command: Command) -> tuple[Command, bool]:
        """Send time-sensitive questions to live sources instead of stale weights."""
        if command.action != "chat" or not self._auto_web_enabled():
            return command, False
        question = str(command.arguments.get("message", "")).strip()
        if not question or not needs_live_information(question):
            return command, False
        return Command("web_research", {"query": question}, raw_text=command.raw_text), True

    def process(self, text: str, spoken: bool = False, on_chunk: Callable[[str], None] | None = None) -> AssistantReply:
        steps = split_commands(text)
        if len(steps) > 1 and all(self._is_action(step) for step in steps):
            messages = [self._process_one(step, spoken).text for step in steps]
            return AssistantReply(" ".join(messages))
        return self._process_one(text, spoken, on_chunk)

    def _bilingual_enabled(self) -> bool:
        return not self.settings_repo or bool(self.settings_repo.get("bilingual_enabled", True))

    def _prepare(self, text: str) -> str:
        """Note the language spoken and rewrite Swahili commands into English.

        Routing stays in one language so every command works in both, while the
        reply is generated in whichever language was used.
        """
        if not self._bilingual_enabled():
            self.last_language = "en"
            return text
        self.last_language = detect(text)
        return to_command_english(text) if self.last_language == SWAHILI else text

    def _language_prompt(self) -> list[dict[str, str]]:
        return [{"role": "system", "content": REPLY_IN_SWAHILI}] if self.last_language == SWAHILI else []

    def _is_action(self, text: str) -> bool:
        """True when a fragment stands on its own as a command, not conversation."""
        command = self.plugins.route(text) if self.plugins else None
        command = command or self.router.route(text)
        return command.action not in {"chat", "noop", "follow_up", "repeat_last"}

    def _process_one(self, text: str, spoken: bool = False, on_chunk: Callable[[str], None] | None = None) -> AssistantReply:
        text = self._prepare(text)
        workflow = self.workflows.match_voice(text) if self.workflows else None
        if workflow:
            result = self.workflows.run(workflow)
            self._last_action_context = f"workflow {workflow} -> {result.message}"
            return AssistantReply(result.message)
        command = self.plugins.route(text) if self.plugins else None
        command = command or self.router.route(text)
        resolved = self._resolve_follow_up(command)
        if isinstance(resolved, AssistantReply):
            return resolved
        command, auto_research = self._upgrade_to_live_answer(resolved)
        if command.action != "chat":
            self._last_command = command
            if command.action == "analyze_screen":
                command.arguments["context"] = self._conversation_context()
            result = self.executor.execute(command)
            details = result.data.get("matches") if result.data else None
            self._last_action_context = f"{command.action} -> {result.message[:240]}"
            if command.action == "semantic_search" and result.success and details:
                context = "\n\n".join(details)
                answer = self._answer([
                    {"role": "system", "content": "Answer only from the supplied local document passages. Cite each source path and page used. Say when the evidence is insufficient."},
                    *self._language_prompt(),
                    *([{"role": "system", "content": VOICE_RESPONSE_PROMPT}] if spoken else []),
                    {"role": "user", "content": f"Question: {command.arguments['query']}\n\nPassages:\n{context}"},
                ], on_chunk)
                return AssistantReply(answer, details)
            if command.action == "read_screen" and result.success and details:
                question = str((result.data or {}).get("query") or "").strip()
                answer = self._answer([
                    {"role": "system", "content": "Text was read from the user's screen by local OCR. Answer using only that text. OCR output can be garbled or out of order, so say when something is unclear rather than guessing."},
                    *self._language_prompt(),
                    *([{"role": "system", "content": VOICE_RESPONSE_PROMPT}] if spoken else []),
                    {"role": "user", "content": f"Question: {question or 'What is on my screen?'}\n\nScreen text:\n{details[0]}"},
                ], on_chunk)
                return AssistantReply(answer)
            if command.action == "web_research" and result.success and details:
                context = "\n\n".join(details)
                answer = self._answer([
                    {"role": "system", "content": "Answer the question using the supplied current web search results. Be clear and useful. Cite supporting URLs inline. Distinguish facts from inference and say when the snippets are insufficient."},
                    *self._language_prompt(),
                    *([{"role": "system", "content": VOICE_RESPONSE_PROMPT}] if spoken else []),
                    {"role": "user", "content": f"Question: {command.arguments['query']}\n\nWeb results:\n{context}"},
                ], on_chunk)
                return AssistantReply(answer, details)
            if not auto_research:
                return AssistantReply(result.message, details)
            # The user asked a normal question, so answer conversationally rather
            # than reporting a search failure they never asked for.
            text = str(command.arguments["query"])
        memory_enabled = self._memory_enabled()
        if memory_enabled:
            self.store.append("user", text)
        history = self.store.recent(limit=self._memory_limit()) if memory_enabled else [{"role": "user", "content": text}]
        messages = [
            {"role": "system", "content": self._system_prompt()},
            *self._language_prompt(),
            *([{"role": "system", "content": VOICE_RESPONSE_PROMPT}] if spoken else []),
            *history,
        ]
        reply = self._answer(messages, on_chunk)
        if memory_enabled:
            self.store.append("assistant", reply)
        return AssistantReply(reply)


@dataclass(frozen=True)
class VoiceConfig:
    """Tunable microphone behaviour so natural pauses do not truncate speech."""

    model: str = "base"
    energy: int = 180
    pause: float = 1.25
    timeout: int = 18
    continuation_timeout: int = 6
    continuation_passes: int = 2
    dynamic_energy: bool = True
    hallucinate_threshold: int = 140
    extended_listening: bool = True
    mic_index: int | None = None
    # faster_whisper runs the same models through CTranslate2 with int8 weights,
    # which matters a lot on a CPU-only machine. whisper_mic falls back to the
    # reference implementation on its own if the library is missing.
    implementation: str = "faster_whisper"

    @classmethod
    def from_settings(cls, settings_repo=None, fallback_model: str = "base") -> "VoiceConfig":
        if not settings_repo:
            return cls(model=fallback_model)
        return cls(
            implementation=str(settings_repo.get("stt_backend", "faster_whisper")),
            model=str(settings_repo.get("whisper_model", fallback_model)),
            energy=int(settings_repo.get("mic_energy", 180)),
            pause=float(settings_repo.get("mic_pause", 1.25)),
            timeout=int(settings_repo.get("mic_timeout", 18)),
            continuation_timeout=int(settings_repo.get("mic_continuation_timeout", 6)),
            continuation_passes=int(settings_repo.get("mic_continuation_passes", 2)),
            dynamic_energy=bool(settings_repo.get("mic_dynamic_energy", True)),
            hallucinate_threshold=int(settings_repo.get("mic_hallucinate_threshold", 140)),
            extended_listening=bool(settings_repo.get("mic_extended_listening", True)),
            mic_index=settings_repo.get("mic_device_index"),
        )


class VoiceInput:
    """Lazy Whisper microphone with extended capture for fuller phrases."""

    NO_SPEECH = {"", "[blank_audio]", "[silence]", "(silence)", "thank you for watching"}

    def __init__(self, config: VoiceConfig | None = None, model: str = "base"):
        self.config = config or VoiceConfig(model=model)
        self._microphone = None
        self._lock = threading.Lock()
        self._config_signature: tuple[Any, ...] | None = None

    def _signature(self) -> tuple[Any, ...]:
        config = self.config
        return (
            config.model, config.energy, config.pause, config.dynamic_energy,
            config.hallucinate_threshold, config.mic_index, config.implementation,
        )

    def _ensure_microphone(self) -> None:
        signature = self._signature()
        if self._microphone is not None and self._config_signature == signature:
            return
        import torch
        from whisper_mic import WhisperMic

        config = self.config
        kwargs = {
            "model": config.model, "english": False, "verbose": False,
            "energy": config.energy, "pause": config.pause,
            "dynamic_energy": config.dynamic_energy, "save_file": False,
            "device": "cuda" if torch.cuda.is_available() else "cpu",
            "implementation": config.implementation,
            "hallucinate_threshold": config.hallucinate_threshold,
        }
        if config.mic_index is not None:
            kwargs["mic_index"] = config.mic_index
        self._microphone = WhisperMic(**kwargs)
        self._config_signature = signature

    def _listen_once(self, timeout: int) -> str:
        with self._lock:
            self._ensure_microphone()
            result = self._microphone.listen(timeout=timeout)
        return self.clean_transcript(result)

    def listen(self, timeout: int | None = None, extended: bool | None = None) -> str:
        """Capture a phrase, then keep listening briefly so pauses do not cut it off."""
        config = self.config
        result = self._listen_once(timeout or config.timeout)
        if not result or not (config.extended_listening if extended is None else extended):
            return result
        for _ in range(max(0, config.continuation_passes)):
            continuation = self._listen_once(config.continuation_timeout)
            if not continuation:
                break
            result = f"{result} {continuation}".strip()
        return result

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
        model = settings_repo.get("openai_chat_model", "gpt-4o-mini") if settings_repo else "gpt-4o-mini"
        return OpenAIProvider(settings.openai_api_key, str(model))
    model = settings_repo.get("ollama_model", settings.ollama_model) if settings_repo else settings.ollama_model
    keep_alive = settings_repo.get("model_keep_alive", "30m") if settings_repo else "30m"
    return OllamaProvider(model, str(keep_alive))

"""Privacy-aware screen capture and optional cloud visual analysis."""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

from .commands import ActionResult


VISION_SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S observing the user's screen. Describe what you see clearly and practically. "
    "Focus on active windows, readable text, buttons, errors, progress indicators, and anything the user likely cares about. "
    "If the user asked a specific question, answer it directly from what's visible. "
    "Use a conversational tone, not a robotic inventory. Note uncertainty when text is blurry or partially obscured."
)


class ScreenService:
    def __init__(self, data_dir: Path, settings_repo=None, api_key: str = ""):
        self.data_dir = data_dir
        self.settings_repo = settings_repo
        self.api_key = api_key

    def _vision_model(self) -> str:
        if self.settings_repo:
            return str(self.settings_repo.get("vision_model", "gpt-4o"))
        return "gpt-4o"

    def _build_prompt(self, prompt: str, context: str = "") -> str:
        sections = [VISION_SYSTEM_PROMPT]
        if context.strip():
            sections.append(f"Recent conversation context:\n{context.strip()}")
        sections.append(f"User request: {prompt.strip() or 'Describe the visible screen and any important text or controls.'}")
        return "\n\n".join(sections)

    def capture(
        self,
        analyze: bool = False,
        prompt: str = "Describe the visible screen.",
        context: str = "",
    ) -> ActionResult:
        if self.settings_repo and self.settings_repo.get("privacy_mode", False):
            return ActionResult(False, "Screen capture is blocked while privacy mode is enabled.")
        from PIL import ImageDraw, ImageGrab
        image = ImageGrab.grab(all_screens=True)
        for region in (self.settings_repo.get("screen_mask_regions", []) if self.settings_repo else []):
            if isinstance(region, list) and len(region) == 4:
                ImageDraw.Draw(image).rectangle(tuple(region), fill="black")
        folder = self.data_dir / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"screen-{datetime.now():%Y%m%d-%H%M%S}.png"
        image.save(path)
        if not analyze:
            return ActionResult(True, f"Screenshot saved as {path.name}.", {"matches": [str(path)]})
        if not self.api_key:
            return ActionResult(
                False, "Screen captured locally, but visual analysis requires OPENAI_API_KEY.", {"matches": [str(path)]}
            )
        with path.open("rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("ascii")
        from openai import OpenAI
        response = OpenAI(api_key=self.api_key).chat.completions.create(
            model=self._vision_model(),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": self._build_prompt(prompt, context)},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}", "detail": "high"}},
                ],
            }],
            max_tokens=900,
        )
        answer = response.choices[0].message.content or "The screen could not be described."
        return ActionResult(True, answer.strip(), {"matches": [str(path)]})

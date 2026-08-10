"""Privacy-aware screen capture and optional cloud visual analysis."""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

from .commands import ActionResult


class ScreenService:
    def __init__(self, data_dir: Path, settings_repo=None, api_key: str = ""):
        self.data_dir = data_dir
        self.settings_repo = settings_repo
        self.api_key = api_key

    def capture(self, analyze: bool = False, prompt: str = "Describe the visible screen.") -> ActionResult:
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
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
            ]}],
            max_tokens=500,
        )
        answer = response.choices[0].message.content or "The screen could not be described."
        return ActionResult(True, answer.strip(), {"matches": [str(path)]})

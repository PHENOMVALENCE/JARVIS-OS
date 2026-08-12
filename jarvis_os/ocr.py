"""Screen text extraction using the OCR engine built into Windows.

Reading text off the screen previously required sending a screenshot to a paid
cloud vision model. Windows ships an OCR engine, so the common case of "what
does this say" costs nothing, stays on the machine, and answers in well under
a second.
"""

from __future__ import annotations

import asyncio
from pathlib import Path


class ScreenTextReader:
    """Wraps the Windows.Media.Ocr engine, which needs no key and no network."""

    def available(self) -> bool:
        try:
            return self._engine() is not None
        except Exception:
            return False

    @staticmethod
    def _preload_onnxruntime() -> None:
        """Load onnxruntime before the Windows Runtime is initialised.

        Initialising WinRT first makes the *first* onnxruntime DLL load fail
        with a dynamic link library initialisation error, which silently takes
        out the wake word and the offline voice, both of which run on onnx.
        Once onnxruntime is resident the two coexist, so ordering is the whole
        fix. Measured: reading the screen before the wake word had ever started
        left "Hey Jarvis" permanently unable to load.
        """
        try:
            import onnxruntime  # noqa: F401
        except Exception:
            # Nothing to protect if it is not installed.
            pass

    @classmethod
    def _engine(cls):
        cls._preload_onnxruntime()
        import winrt.windows.media.ocr as ocr
        return ocr.OcrEngine.try_create_from_user_profile_languages()

    async def _read(self, path: Path) -> str:
        import winrt.windows.graphics.imaging as imaging
        import winrt.windows.storage as storage

        engine = self._engine()
        if engine is None:
            raise RuntimeError("No OCR language pack is installed for this user profile.")
        file = await storage.StorageFile.get_file_from_path_async(str(path))
        stream = await file.open_async(storage.FileAccessMode.READ)
        decoder = await imaging.BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await engine.recognize_async(bitmap)
        return (result.text or "").strip()

    def read(self, path: Path | str) -> str:
        """Return every line of text the engine can see in the image."""
        return asyncio.run(self._read(Path(path)))

    @staticmethod
    def summarize(text: str, limit: int = 4000) -> str:
        """Collapse OCR output into something worth putting in front of a model."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        joined = "\n".join(lines)
        return joined[:limit]

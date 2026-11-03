"""OCR for scanned resumes (PDFs that contain only page images).

The engine is chosen with OCR_ENGINE:
  tesseract (default)  needs the Tesseract program installed on the server
                       (Debian/Ubuntu: apt install tesseract-ocr; Windows: UB-Mannheim installer)
  none                 turns OCR off

A vision-model engine can be added as another OCREngine subclass without touching the parser.
"""
import asyncio
import io
import logging
import os
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import List, Optional

logger = logging.getLogger(__name__)


class OCREngine(ABC):
    """Turns page images into text"""

    name: str = "base"

    @abstractmethod
    async def extract_text(self, images: List[bytes]) -> str:
        """Read PNG page images in order and return their combined text"""


class TesseractOCR(OCREngine):
    name = "tesseract"

    def __init__(self, language: str = "eng"):
        import pytesseract  # imported here so the app runs without the package
        self._pytesseract = pytesseract
        self._language = language
        # Raises if the Tesseract program itself is missing
        self._version = str(pytesseract.get_tesseract_version())

    def _read(self, images: List[bytes]) -> str:
        from PIL import Image
        pages = []
        for png in images:
            with Image.open(io.BytesIO(png)) as image:
                pages.append(self._pytesseract.image_to_string(image, lang=self._language))
        return "\n".join(pages)

    async def extract_text(self, images: List[bytes]) -> str:
        # Tesseract is CPU bound; keep it off the event loop
        return await asyncio.to_thread(self._read, images)


@lru_cache(maxsize=1)
def get_ocr_engine() -> Optional[OCREngine]:
    """The configured engine, or None when OCR is off or not installed"""
    choice = os.getenv("OCR_ENGINE", "tesseract").lower()
    if choice == "none":
        return None
    if choice == "tesseract":
        try:
            engine = TesseractOCR(language=os.getenv("OCR_LANG", "eng"))
            logger.info(f"OCR enabled: tesseract {engine._version}")
            return engine
        except Exception as e:
            logger.warning(f"OCR unavailable, scanned PDFs will be rejected: {e}")
            return None
    raise ValueError(f"Unknown OCR_ENGINE '{choice}'. Use 'tesseract' or 'none'.")

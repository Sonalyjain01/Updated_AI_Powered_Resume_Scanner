import shutil

import pytest

import file_processor
import ocr
from file_processor import FileProcessor
from tests.conftest import RESUME_TEXT, make_pdf, make_scanned_pdf


class FakeOCR(ocr.OCREngine):
    name = "fake-ocr"

    def __init__(self, text=RESUME_TEXT, error=None):
        self.text, self.error, self.page_counts = text, error, []

    async def extract_text(self, images):
        self.page_counts.append(len(images))
        if self.error:
            raise self.error
        return self.text


def use_engine(monkeypatch, engine):
    monkeypatch.setattr(file_processor, "get_ocr_engine", lambda: engine)


class TestFallbackLogic:
    async def test_text_pdf_never_uses_ocr(self, monkeypatch):
        engine = FakeOCR()
        use_engine(monkeypatch, engine)
        result = await FileProcessor.extract_document(make_pdf(), "cv.pdf")
        assert result.used_ocr is False and engine.page_counts == []

    async def test_image_only_pdf_uses_ocr(self, monkeypatch):
        use_engine(monkeypatch, FakeOCR())
        result = await FileProcessor.extract_document(make_scanned_pdf(), "scan.pdf")
        assert result.used_ocr is True and result.text == RESUME_TEXT

    async def test_image_only_pdf_without_ocr_explains_why(self, monkeypatch):
        use_engine(monkeypatch, None)
        with pytest.raises(ValueError, match="looks like a scan.*OCR"):
            await FileProcessor.extract_document(make_scanned_pdf(), "scan.pdf")

    async def test_ocr_that_finds_nothing_is_reported(self, monkeypatch):
        use_engine(monkeypatch, FakeOCR(text="   "))
        with pytest.raises(ValueError, match="even with text recognition"):
            await FileProcessor.extract_document(make_scanned_pdf(), "scan.pdf")

    async def test_ocr_crash_is_reported_not_raised_raw(self, monkeypatch):
        use_engine(monkeypatch, FakeOCR(error=RuntimeError("tesseract exploded")))
        with pytest.raises(ValueError, match="even with text recognition"):
            await FileProcessor.extract_document(make_scanned_pdf(), "scan.pdf")

    async def test_page_limit(self, monkeypatch):
        import fitz
        pdf = fitz.open()
        for _ in range(8):
            pdf.new_page()
        engine = FakeOCR()
        use_engine(monkeypatch, engine)
        monkeypatch.setattr(FileProcessor, "OCR_MAX_PAGES", 3)
        await FileProcessor.extract_document(pdf.tobytes(), "many.pdf")
        assert engine.page_counts == [3]

    async def test_short_text_layer_is_replaced_by_longer_ocr_result(self, monkeypatch):
        use_engine(monkeypatch, FakeOCR())
        result = await FileProcessor.extract_document(make_pdf("Resume"), "cv.pdf")
        assert result.used_ocr is True and result.text == RESUME_TEXT

    async def test_text_layer_wins_when_ocr_finds_less(self, monkeypatch):
        use_engine(monkeypatch, FakeOCR(text="x"))
        result = await FileProcessor.extract_document(make_pdf("Short real text"), "cv.pdf")
        assert result.used_ocr is False and "Short real text" in result.text


class TestEngineSelection:
    def test_none_disables_ocr(self, monkeypatch):
        monkeypatch.setenv("OCR_ENGINE", "none")
        ocr.get_ocr_engine.cache_clear()
        assert ocr.get_ocr_engine() is None

    def test_unknown_engine_is_rejected(self, monkeypatch):
        monkeypatch.setenv("OCR_ENGINE", "magic")
        ocr.get_ocr_engine.cache_clear()
        with pytest.raises(ValueError, match="Unknown OCR_ENGINE"):
            ocr.get_ocr_engine()
        ocr.get_ocr_engine.cache_clear()

    def test_missing_tesseract_degrades_to_none(self, monkeypatch):
        def broken(*args, **kwargs):
            raise RuntimeError("tesseract is not installed")
        monkeypatch.setenv("OCR_ENGINE", "tesseract")
        monkeypatch.setattr(ocr, "TesseractOCR", broken)
        ocr.get_ocr_engine.cache_clear()
        assert ocr.get_ocr_engine() is None
        ocr.get_ocr_engine.cache_clear()


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed")
class TestRealTesseract:
    async def test_reads_a_scanned_resume(self, monkeypatch):
        use_engine(monkeypatch, ocr.TesseractOCR())
        result = await FileProcessor.extract_document(make_scanned_pdf(), "scan.pdf")
        assert result.used_ocr is True
        for word in ("Jane Doe", "FastAPI", "MongoDB"):
            assert word in result.text

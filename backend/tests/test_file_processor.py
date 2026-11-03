import io
import zipfile

import pytest

from file_processor import FileProcessor
from tests.conftest import RESUME_TEXT, make_docx, make_encrypted_pdf, make_pdf


class TestExtensions:
    @pytest.mark.parametrize("name,expected", [
        ("cv.pdf", True), ("CV.PDF", True), ("cv.docx", True),
        ("cv.doc", False), ("cv.txt", False), ("cv", False), ("", False), (None, False),
    ])
    def test_is_supported_file(self, name, expected):
        assert FileProcessor.is_supported_file(name) is expected


class TestMimeType:
    def test_matching_type_passes(self):
        FileProcessor.validate_mime_type("application/pdf", "cv.pdf")

    def test_charset_suffix_is_ignored(self):
        FileProcessor.validate_mime_type("application/pdf; charset=binary", "cv.pdf")

    @pytest.mark.parametrize("declared", ["application/octet-stream", "", None])
    def test_generic_type_defers_to_magic_bytes(self, declared):
        FileProcessor.validate_mime_type(declared, "cv.pdf")

    def test_mismatched_type_is_rejected(self):
        with pytest.raises(ValueError, match="does not match"):
            FileProcessor.validate_mime_type("text/html", "cv.pdf")


class TestMagicBytes:
    def test_pdf(self):
        assert FileProcessor.validate_magic_bytes(make_pdf(), "cv.pdf") == "pdf"

    def test_docx(self):
        assert FileProcessor.validate_magic_bytes(make_docx(), "cv.docx") == "docx"

    def test_pdf_renamed_to_docx_is_rejected(self):
        with pytest.raises(ValueError, match="not .pdf"):
            FileProcessor.validate_magic_bytes(make_pdf(), "cv.docx")

    def test_docx_renamed_to_pdf_is_rejected(self):
        with pytest.raises(ValueError, match="extension is not .docx"):
            FileProcessor.validate_magic_bytes(make_docx(), "cv.pdf")

    def test_random_bytes_are_rejected(self):
        with pytest.raises(ValueError, match="does not look like"):
            FileProcessor.validate_magic_bytes(b"MZ\x90\x00 not a document", "cv.pdf")

    def test_legacy_word_signature_is_rejected_with_guidance(self):
        with pytest.raises(ValueError, match="Save As"):
            FileProcessor.validate_magic_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 50, "cv.docx")

    def test_zip_that_is_not_word_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("readme.txt", "hello")
        with pytest.raises(ValueError, match="not a valid DOCX"):
            FileProcessor.validate_magic_bytes(buffer.getvalue(), "cv.docx")

    def test_zip_bomb_is_rejected(self, monkeypatch):
        monkeypatch.setattr(FileProcessor, "MAX_DOCX_UNCOMPRESSED_SIZE", 10)
        with pytest.raises(ValueError, match="unreasonable size"):
            FileProcessor.validate_magic_bytes(make_docx(), "cv.docx")


class TestExtraction:
    async def test_pdf_text(self):
        text = await FileProcessor.extract_text_from_file(make_pdf(), "cv.pdf")
        assert "Jane Doe" in text and "FastAPI" in text

    async def test_docx_text(self):
        text = await FileProcessor.extract_text_from_file(make_docx(), "cv.docx")
        assert RESUME_TEXT in text

    async def test_password_protected_pdf_is_rejected(self):
        with pytest.raises(ValueError, match="password-protected"):
            await FileProcessor.extract_text_from_file(make_encrypted_pdf(), "cv.pdf")

    async def test_oversized_file_is_rejected(self, monkeypatch):
        monkeypatch.setattr(FileProcessor, "MAX_FILE_SIZE", 100)
        with pytest.raises(ValueError, match="exceeds maximum"):
            await FileProcessor.extract_text_from_file(make_pdf(), "cv.pdf")

    async def test_unsupported_extension_is_rejected(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            await FileProcessor.extract_text_from_file(b"x", "cv.doc")

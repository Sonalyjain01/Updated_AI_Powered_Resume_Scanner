import io
import os
import zipfile
from typing import NamedTuple, Optional
import fitz  # PyMuPDF
from docx import Document
import logging

from ocr import get_ocr_engine

logger = logging.getLogger(__name__)


56class ExtractedText(NamedTuple):
    text: str
    used_ocr: bool = False


class FileProcessor:
    """Handle file processing for PDF and DOCX files"""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.docx'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_DOCX_UNCOMPRESSED_SIZE = 50 * 1024 * 1024  # zip-bomb guard

    # OCR runs only when a PDF has less selectable text than this, and reads at most
    # OCR_MAX_PAGES pages so one upload cannot tie up the server.
    OCR_MIN_TEXT_CHARS = 100
    OCR_MAX_PAGES = int(os.getenv('OCR_MAX_PAGES', '5'))
    OCR_DPI = int(os.getenv('OCR_DPI', '200'))

    # Content types browsers send for each extension. Some clients send
    # application/octet-stream, so that is accepted and the magic bytes decide.
    ALLOWED_MIME_TYPES = {
        '.pdf': {'application/pdf', 'application/x-pdf'},
        '.docx': {
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/zip',
        },
    }
    GENERIC_MIME_TYPES = {'application/octet-stream', ''}

    PDF_MAGIC = b'%PDF-'
    ZIP_MAGIC = b'PK\x03\x04'
    OLE_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'  # legacy .doc and encrypted .docx, both unsupported

    @classmethod
    def is_supported_file(cls, filename: str) -> bool:
        """Check if file extension is supported"""
        _, ext = os.path.splitext((filename or '').lower())
        return ext in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def validate_file_size(cls, file_content: bytes) -> bool:
        """Validate file size"""
        return len(file_content) <= cls.MAX_FILE_SIZE

    @classmethod
    def validate_mime_type(cls, content_type: Optional[str], filename: str) -> None:
        """Reject uploads whose declared content type does not match the extension"""
        _, ext = os.path.splitext((filename or '').lower())
        declared = (content_type or '').split(';')[0].strip().lower()
        if declared in cls.GENERIC_MIME_TYPES:
            return
        if declared not in cls.ALLOWED_MIME_TYPES.get(ext, set()):
            raise ValueError(
                f"File content type '{declared}' does not match a {ext} file. "
                "Upload a PDF or DOCX resume."
            )

    @classmethod
    def validate_magic_bytes(cls, file_content: bytes, filename: str) -> str:
        """Check the real file signature and return the detected kind ('pdf' or 'docx')"""
        _, ext = os.path.splitext((filename or '').lower())
        head = file_content[:8]

        if head.startswith(cls.PDF_MAGIC):
            if ext != '.pdf':
                raise ValueError("File content is a PDF but the extension is not .pdf")
            return 'pdf'

        if head.startswith(cls.ZIP_MAGIC):
            if ext != '.docx':
                raise ValueError("File content is a Word document but the extension is not .docx")
            cls._validate_docx_archive(file_content)
            return 'docx'

        if head.startswith(cls.OLE_MAGIC):
            raise ValueError(
                "Legacy .doc files and password-protected Word documents are not supported. "
                "In Word, use Save As to save the resume as an unprotected .docx or PDF, then upload it again."
            )

        raise ValueError(
            "File content does not look like a PDF or DOCX. "
            "The file may be corrupted or renamed from another format."
        )

    @classmethod
    def _validate_docx_archive(cls, file_content: bytes) -> None:
        """Confirm the zip is a real Word package and not a zip bomb"""
        try:
            with zipfile.ZipFile(io.BytesIO(file_content)) as archive:
                names = set(archive.namelist())
                if 'word/document.xml' not in names:
                    raise ValueError("File is a zip archive but not a valid DOCX document")
                if sum(info.file_size for info in archive.infolist()) > cls.MAX_DOCX_UNCOMPRESSED_SIZE:
                    raise ValueError("DOCX file expands to an unreasonable size")
        except zipfile.BadZipFile:
            raise ValueError("DOCX file is corrupted or not a valid zip archive")

    @classmethod
    async def extract_text_from_pdf(cls, file_content: bytes) -> str:
        """Extract text from PDF file"""
        return (await cls.extract_pdf(file_content)).text

    @classmethod
    async def extract_pdf(cls, file_content: bytes) -> ExtractedText:
        """Extract text from a PDF, falling back to OCR when it has little or no selectable text"""
        try:
            doc = fitz.open(stream=io.BytesIO(file_content), filetype="pdf")

            if doc.needs_pass or doc.is_encrypted:
                doc.close()
                raise ValueError(
                    "PDF is password-protected. Remove the password and upload it again."
                )

            try:
                full_text = chr(10).join(page.get_text() for page in doc)

                if len(full_text.strip()) >= cls.OCR_MIN_TEXT_CHARS:
                    logger.info(f"Successfully extracted {len(full_text)} characters from PDF")
                    return ExtractedText(full_text, False)

                ocr_text = await cls._ocr_pdf(doc)
            finally:
                doc.close()

            # Keep whichever read found more, in case the PDF mixes real text and scans
            best = ocr_text if len(ocr_text.strip()) > len(full_text.strip()) else full_text
            if not best.strip():
                raise ValueError(cls._no_text_message())
            return ExtractedText(best, best is ocr_text)

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise ValueError(f"Failed to process PDF file: {str(e)}")

    @classmethod
    def _no_text_message(cls) -> str:
        if get_ocr_engine() is None:
            return (
                "This PDF has no selectable text, so it looks like a scan, and text recognition (OCR) "
                "is not available on this server. Upload a text-based PDF or a DOCX."
            )
        return "No text could be read from this PDF, even with text recognition. Upload a clearer copy."

    @classmethod
    async def _ocr_pdf(cls, doc) -> str:
        """OCR the first pages of an open PDF; returns '' when OCR is off or fails"""
        engine = get_ocr_engine()
        if engine is None:
            return ""
        pages = min(len(doc), cls.OCR_MAX_PAGES)
        if len(doc) > pages:
            logger.warning(f"OCR limited to the first {pages} of {len(doc)} pages")
        try:
            images = [doc[i].get_pixmap(dpi=cls.OCR_DPI).tobytes("png") for i in range(pages)]
            text = await engine.extract_text(images)
            logger.info(f"OCR ({engine.name}) read {len(text)} characters from {pages} page(s)")
            return text
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""

    @classmethod
    async def extract_text_from_docx(cls, file_content: bytes) -> str:
        """Extract text from DOCX file"""
        try:
            # Create a file-like object from bytes
            docx_stream = io.BytesIO(file_content)
            
            # Open DOCX with python-docx
            doc = Document(docx_stream)
            
            text_content = []
            
            # Extract text from paragraphs
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text.strip())
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            text_content.append(cell.text.strip())
            
            # Join all content
            full_text = "\n".join(text_content)
            
            if not full_text.strip():
                raise ValueError("No text content found in DOCX")
            
            logger.info(f"Successfully extracted {len(full_text)} characters from DOCX")
            return full_text
            
        except Exception as e:
            logger.error(f"Error extracting text from DOCX: {str(e)}")
            raise ValueError(f"Failed to process DOCX file: {str(e)}")
    
    @classmethod
    async def extract_text_from_file(cls, file_content: bytes, filename: str) -> str:
        """Extract text from file based on its detected content type"""
        return (await cls.extract_document(file_content, filename)).text

    @classmethod
    async def extract_document(cls, file_content: bytes, filename: str) -> ExtractedText:
        """Like extract_text_from_file, but also reports whether OCR was needed"""
        if not cls.validate_file_size(file_content):
            raise ValueError(f"File size exceeds maximum limit of {cls.MAX_FILE_SIZE // (1024*1024)}MB")

        if not cls.is_supported_file(filename):
            raise ValueError(f"Unsupported file type. Supported types: {', '.join(sorted(cls.SUPPORTED_EXTENSIONS))}")

        try:
            # The file signature decides the parser, not the extension
            kind = cls.validate_magic_bytes(file_content, filename)
            if kind == 'pdf':
                return await cls.extract_pdf(file_content)
            return ExtractedText(await cls.extract_text_from_docx(file_content), False)

        except Exception as e:
            logger.error(f"File processing error for {filename}: {str(e)}")
            raise

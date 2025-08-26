import io
import os
from typing import Optional
import fitz  # PyMuPDF
from docx import Document
import logging

logger = logging.getLogger(__name__)

class FileProcessor:
    """Handle file processing for PDF and DOCX files"""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.doc'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @classmethod
    def is_supported_file(cls, filename: str) -> bool:
        """Check if file extension is supported"""
        _, ext = os.path.splitext(filename.lower())
        return ext in cls.SUPPORTED_EXTENSIONS
    
    @classmethod
    def validate_file_size(cls, file_content: bytes) -> bool:
        """Validate file size"""
        return len(file_content) <= cls.MAX_FILE_SIZE
    
    @classmethod
    async def extract_text_from_pdf(cls, file_content: bytes) -> str:
        """Extract text from PDF file"""
        try:
            # Create a file-like object from bytes
            pdf_stream = io.BytesIO(file_content)
            
            # Open PDF with PyMuPDF
            doc = fitz.open(stream=pdf_stream, filetype="pdf")
            
            text_content = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                text_content.append(text)
            
            doc.close()
            
            # Join all pages
            full_text = "\n".join(text_content)
            
            if not full_text.strip():
                raise ValueError("No text content found in PDF")
            
            logger.info(f"Successfully extracted {len(full_text)} characters from PDF")
            return full_text
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise ValueError(f"Failed to process PDF file: {str(e)}")
    
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
        """Extract text from file based on extension"""
        if not cls.validate_file_size(file_content):
            raise ValueError(f"File size exceeds maximum limit of {cls.MAX_FILE_SIZE // (1024*1024)}MB")
        
        if not cls.is_supported_file(filename):
            raise ValueError(f"Unsupported file type. Supported types: {', '.join(cls.SUPPORTED_EXTENSIONS)}")
        
        # Get file extension
        _, ext = os.path.splitext(filename.lower())
        
        try:
            if ext == '.pdf':
                return await cls.extract_text_from_pdf(file_content)
            elif ext in ['.docx', '.doc']:
                return await cls.extract_text_from_docx(file_content)
            else:
                raise ValueError(f"Unsupported file extension: {ext}")
                
        except Exception as e:
            logger.error(f"File processing error for {filename}: {str(e)}")
            raise
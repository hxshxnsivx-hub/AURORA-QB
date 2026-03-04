"""
PDF Parser using PyPDF2

Extracts text content from PDF files for question bank processing.
"""

from typing import Optional
import PyPDF2
from io import BytesIO

from utils.logger import get_logger

logger = get_logger(__name__)


class PDFParser:
    """Parser for PDF files"""
    
    @staticmethod
    def parse(file_content: bytes, file_name: str) -> str:
        """
        Parse PDF file and extract text content
        
        Args:
            file_content: Raw bytes of the PDF file
            file_name: Name of the file (for logging)
            
        Returns:
            Extracted text content
            
        Raises:
            Exception: If parsing fails
        """
        try:
            logger.info(f"Parsing PDF file: {file_name}")
            
            # Create a BytesIO object from the file content
            pdf_file = BytesIO(file_content)
            
            # Create PDF reader
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Check if PDF is encrypted
            if pdf_reader.is_encrypted:
                raise Exception("PDF file is encrypted and cannot be parsed")
            
            # Extract text from all pages
            text_content = []
            num_pages = len(pdf_reader.pages)
            
            logger.info(f"PDF has {num_pages} pages")
            
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                
                if page_text:
                    text_content.append(page_text)
            
            # Join all pages with double newline
            full_text = "\n\n".join(text_content)
            
            if not full_text.strip():
                raise Exception("No text content could be extracted from PDF")
            
            logger.info(
                f"Successfully parsed PDF: {file_name}",
                extra={
                    "file_name": file_name,
                    "num_pages": num_pages,
                    "text_length": len(full_text)
                }
            )
            
            return full_text
            
        except PyPDF2.errors.PdfReadError as e:
            logger.error(f"PDF read error for {file_name}: {str(e)}")
            raise Exception(f"Failed to read PDF file: {str(e)}")
        except Exception as e:
            logger.error(f"PDF parsing error for {file_name}: {str(e)}")
            raise Exception(f"Failed to parse PDF file: {str(e)}")

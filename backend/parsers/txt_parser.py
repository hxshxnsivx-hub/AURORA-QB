"""
TXT Parser

Extracts text content from plain text files for question bank processing.
"""

from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class TXTParser:
    """Parser for TXT files"""
    
    @staticmethod
    def parse(file_content: bytes, file_name: str) -> str:
        """
        Parse TXT file and extract text content
        
        Args:
            file_content: Raw bytes of the TXT file
            file_name: Name of the file (for logging)
            
        Returns:
            Extracted text content
            
        Raises:
            Exception: If parsing fails
        """
        try:
            logger.info(f"Parsing TXT file: {file_name}")
            
            # Try different encodings
            encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
            
            text_content = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    text_content = file_content.decode(encoding)
                    used_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue
            
            if text_content is None:
                raise Exception("Could not decode text file with any supported encoding")
            
            if not text_content.strip():
                raise Exception("Text file is empty")
            
            logger.info(
                f"Successfully parsed TXT: {file_name}",
                extra={
                    "file_name": file_name,
                    "encoding": used_encoding,
                    "text_length": len(text_content)
                }
            )
            
            return text_content
            
        except Exception as e:
            logger.error(f"TXT parsing error for {file_name}: {str(e)}")
            raise Exception(f"Failed to parse TXT file: {str(e)}")

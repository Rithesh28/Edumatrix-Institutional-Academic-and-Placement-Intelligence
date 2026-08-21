"""
Parser Factory for Exam Duty Extraction

This module provides a factory class that determines which parser
to use based on the file type/extension.
"""

from typing import Optional
from .base_parser import BaseParser
from .pdf_parser import PDFParser
from .image_parser import ImageParser


class ParserFactory:
    """
    Factory class to create appropriate parser instances.
    
    Supported file types:
    - PDF: .pdf
    - Images: .jpg, .jpeg, .png
    - DOCX: .docx
    """
    
    # Supported file extensions and their corresponding parser classes
    PARSER_MAP = {
        '.pdf': PDFParser,
        '.jpg': ImageParser,
        '.jpeg': ImageParser,
        '.png': ImageParser,
        '.docx': ImageParser,  # We'll use ImageParser for DOCX too (handles text extraction)
    }
    
    @classmethod
    def get_parser(cls, file_path: str) -> Optional[BaseParser]:
        """
        Get the appropriate parser for the given file.
        
        Args:
            file_path: Path to the file to parse
            
        Returns:
            Instance of the appropriate parser, or None if unsupported
            
        Raises:
            ValueError: If file type is unsupported
        """
        import os
        ext = os.path.splitext(file_path)[1].lower()
        
        parser_class = cls.PARSER_MAP.get(ext)
        
        if not parser_class:
            raise ValueError(f"Unsupported file type: {ext}. Supported types: {list(cls.PARSER_MAP.keys())}")
        
        return parser_class(file_path)
    
    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """
        Check if the file type is supported.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if supported, False otherwise
        """
        import os
        ext = os.path.splitext(file_path)[1].lower()
        return ext in cls.PARSER_MAP
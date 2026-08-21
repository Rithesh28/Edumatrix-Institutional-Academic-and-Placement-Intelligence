"""
Abstract Base Parser for Exam Duty Extraction

This module defines the base interface that all exam duty parsers must implement.
Each parser handles a specific file type (PDF, Image, DOCX) and returns
structured data that can be processed by the duty creator.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class BaseParser(ABC):
    """
    Abstract base class for all exam duty parsers.
    
    All parsers must implement:
    - parse(): Main entry point for parsing
    - extract_text(): Extract raw text from file
    - get_metadata(): Get file metadata
    """
    
    def __init__(self, file_path: str):
        """
        Initialize parser with file path.
        
        Args:
            file_path: Path to the file to parse
        """
        self.file_path = file_path
        self.metadata = {}
        self._parsed_data = None
    
    @abstractmethod
    def parse(self) -> Dict[str, Any]:
        """
        Parse the file and return structured data.
        
        Returns:
            Dict containing parsed data:
            {
                'raw_text': str,
                'tables': List[Dict],
                'entities': Dict,
                'metadata': Dict,
                'checkmarks': List[Dict]
            }
        """
        pass
    
    @abstractmethod
    def extract_text(self) -> str:
        """
        Extract raw text from the file.
        
        Returns:
            Extracted text as string
        """
        pass
    
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get file metadata (size, type, page count, etc.).
        
        Returns:
            Dict with metadata
        """
        pass
    
    def get_file_extension(self) -> str:
        """
        Get file extension from file path.
        
        Returns:
            File extension (e.g., '.pdf', '.jpg')
        """
        import os
        return os.path.splitext(self.file_path)[1].lower()
    
    def get_file_size(self) -> int:
        """
        Get file size in bytes.
        
        Returns:
            File size in bytes
        """
        import os
        return os.path.getsize(self.file_path)
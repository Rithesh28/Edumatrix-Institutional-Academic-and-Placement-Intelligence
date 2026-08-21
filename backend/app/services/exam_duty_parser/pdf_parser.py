"""
PDF Parser for Exam Duty Extraction

This module handles parsing of text-based PDF files for exam duty schedules.
It uses pdfplumber for text extraction with layout preservation.
"""

import os
import re
from typing import Dict, Any, List, Optional
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
import logging
from .base_parser import BaseParser

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """
    Parser for text-based PDF files.
    
    Features:
    - Extracts text with layout preservation
    - Detects tables in the PDF
    - Preserves page structure
    - Handles multi-page PDFs
    - Handles complex VTU duty charts
    """
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self._pdf = None
        self._pages = []
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse the PDF and return structured data.
        
        Returns:
            Dict containing parsed data
        """
        try:
            logger.info(f"Parsing PDF: {self.file_path}")
            
            with pdfplumber.open(self.file_path) as pdf:
                self._pdf = pdf
                self._pages = pdf.pages
                
                full_text = ""
                all_tables = []
                
                for page_num, page in enumerate(pdf.pages):
                    logger.info(f"Processing page {page_num + 1}")
                    
                    # Extract text
                    page_text = page.extract_text() or ""
                    full_text += page_text + "\n"
                    
                    # Extract tables with better settings
                    try:
                        tables = page.extract_tables({
                            "vertical_strategy": "text",
                            "horizontal_strategy": "text",
                            "snap_tolerance": 3,
                        })
                        
                        if tables:
                            for table in tables:
                                if table and len(table) > 0:
                                    # Clean the table
                                    cleaned_table = self._clean_table(table)
                                    if cleaned_table and len(cleaned_table) > 1:
                                        all_tables.append(cleaned_table)
                                        logger.info(f"Extracted table with {len(cleaned_table)} rows")
                    except Exception as e:
                        logger.warning(f"Table extraction failed on page {page_num + 1}: {str(e)}")
                
                # If no tables found, try text-based parsing
                if not all_tables:
                    logger.info("No tables found, trying text-based parsing...")
                    all_tables = self._extract_tables_from_text(full_text)
                
                return {
                    'raw_text': full_text,
                    'tables': all_tables,
                    'pages': [{'page_num': i + 1, 'text': page.extract_text() or ""} 
                             for i, page in enumerate(pdf.pages)],
                    'metadata': self.get_metadata(),
                    'file_type': 'pdf'
                }
                
        except Exception as e:
            logger.error(f"Failed to parse PDF: {str(e)}")
            raise Exception(f"Failed to parse PDF: {str(e)}")
    
    def _clean_table(self, table: List[List[str]]) -> List[List[str]]:
        """Clean and normalize table data."""
        cleaned = []
        for row in table:
            if row:
                cleaned_row = [
                    str(cell).strip() if cell else "" 
                    for cell in row
                ]
                # Skip empty rows
                if any(cleaned_row):
                    cleaned.append(cleaned_row)
        return cleaned
    
    def _extract_tables_from_text(self, text: str) -> List[List[List[str]]]:
        """
        Extract tables from raw text (fallback method).
        
        This handles cases where pdfplumber can't detect tables.
        """
        tables = []
        lines = text.split('\n')
        
        # Look for table patterns
        current_table = []
        in_table = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line looks like a table row (has multiple columns)
            # Look for patterns like: "Name | Date | Time" or multiple spaces
            has_pipe = '|' in line
            has_multiple_spaces = len(line.split()) > 3 and '  ' in line
            
            if has_pipe or has_multiple_spaces:
                in_table = True
                if has_pipe:
                    cells = [cell.strip() for cell in line.split('|')]
                else:
                    cells = re.split(r'\s{2,}', line)
                cells = [c for c in cells if c]
                if cells:
                    current_table.append(cells)
            else:
                if in_table and len(current_table) > 1:
                    tables.append(current_table)
                current_table = []
                in_table = False
        
        if in_table and len(current_table) > 1:
            tables.append(current_table)
        
        return tables
    
    def extract_text(self) -> str:
        """Extract raw text from the PDF."""
        try:
            with pdfplumber.open(self.file_path) as pdf:
                full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
                return full_text
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {str(e)}")
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get PDF metadata."""
        try:
            with pdfplumber.open(self.file_path) as pdf:
                return {
                    'file_name': os.path.basename(self.file_path),
                    'file_size': self.get_file_size(),
                    'file_type': 'pdf',
                    'pages': len(pdf.pages),
                    'metadata': pdf.metadata if pdf.metadata else {}
                }
        except Exception:
            return {
                'file_name': os.path.basename(self.file_path),
                'file_size': self.get_file_size(),
                'file_type': 'pdf',
                'pages': 0,
                'metadata': {}
            }
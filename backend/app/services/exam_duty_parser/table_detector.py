"""
Table Detector for Exam Duty Extraction

This module detects table structures in text or images.
It identifies:
- Table boundaries
- Row and column structure
- Header cells
- Data cells
"""

from typing import Dict, List, Any, Optional, Tuple
import re


class TableDetector:
    """
    Detects table structures in text.
    
    Features:
    - Detects tabular data using patterns
    - Identifies rows and columns
    - Extracts header information
    - Handles merged cells (basic)
    """
    
    def __init__(self):
        """Initialize table detector."""
        self._tables = []
    
    def detect(self, text: str) -> List[List[str]]:
        """
        Detect tables in text.
        
        Args:
            text: Text to search for tables
            
        Returns:
            List of tables, each table is a list of rows
        """
        # Split into lines
        lines = text.split('\n')
        
        # Find potential tables
        tables = []
        current_table = []
        
        for line in lines:
            # Check if line looks like a table row
            if self._is_table_row(line):
                # Parse row into cells
                cells = self._parse_row(line)
                if cells:
                    current_table.append(cells)
            else:
                # End of table
                if len(current_table) > 1:  # Minimum 2 rows to be a table
                    tables.append(current_table)
                current_table = []
        
        # Don't forget the last table
        if len(current_table) > 1:
            tables.append(current_table)
        
        return tables
    
    def _is_table_row(self, line: str) -> bool:
        """
        Check if a line looks like a table row.
        
        Criteria:
        - Contains separators (|, \t, multiple spaces)
        - Or contains multiple columns of data
        """
        if not line:
            return False
        
        # Check for pipe separator
        if '|' in line:
            return True
        
        # Check for tab separator
        if '\t' in line:
            return True
        
        # Check for multiple spaces (at least 3 spaces)
        if re.search(r' {3,}', line):
            return True
        
        return False
    
    def _parse_row(self, row: str) -> List[str]:
        """
        Parse a table row into cells.
        
        Returns:
            List of cell contents
        """
        # Remove leading/trailing whitespace
        row = row.strip()
        
        # Split by pipe
        if '|' in row:
            cells = [cell.strip() for cell in row.split('|')]
            # Remove empty cells at ends
            if cells and not cells[0]:
                cells = cells[1:]
            if cells and not cells[-1]:
                cells = cells[:-1]
            return cells
        
        # Split by tab
        if '\t' in row:
            return [cell.strip() for cell in row.split('\t')]
        
        # Split by multiple spaces
        if re.search(r' {3,}', row):
            cells = re.split(r' {2,}', row)
            return [cell.strip() for cell in cells if cell.strip()]
        
        return [row]
    
    def detect_header_row(self, table: List[List[str]]) -> int:
        """
        Detect the header row in a table.
        
        Args:
            table: 2D list representing the table
            
        Returns:
            Index of the header row, or -1 if not found
        """
        if not table:
            return -1
        
        # Check first row for date/time patterns
        date_pattern = r'\d{1,2}\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)'
        time_pattern = r'\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?'
        
        for i, row in enumerate(table):
            row_text = " ".join(str(cell) for cell in row)
            if re.search(date_pattern, row_text) or re.search(time_pattern, row_text):
                return i
        
        # If no date/time found, assume first row is header
        return 0
    
    def extract_cells(self, table: List[List[str]]) -> List[Dict]:
        """
        Extract cells with position information.
        
        Returns:
            List of dicts with row, col, and content
        """
        cells = []
        for row_idx, row in enumerate(table):
            for col_idx, cell in enumerate(row):
                cells.append({
                    'row': row_idx,
                    'col': col_idx,
                    'content': cell
                })
        return cells
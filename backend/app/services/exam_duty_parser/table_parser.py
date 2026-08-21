"""
Table Parser for Exam Duty Extraction

This module handles parsing of tabular data from exam duty schedules.
It identifies table structure, headers, and maps checkmarks to duties.
"""

from typing import Dict, Any, List, Optional, Tuple
import re
import logging
from .checkmark_detector import CheckmarkDetector
from .entity_mapper import EntityMapper

logger = logging.getLogger(__name__)


class TableParser:
    """
    Parser for tabular exam duty data.
    """
    
    def __init__(self):
        self.checkmark_detector = CheckmarkDetector()
        self.entity_mapper = EntityMapper()
    
    def parse_table(self, table_data: List[List[str]], raw_text: str = "", valid_dates: List[str] = None) -> Dict[str, Any]:
        """Parse a table and extract duty information."""
        if not table_data or len(table_data) == 0:
            logger.warning("Empty table data received")
            return {'headers': [], 'faculty_rows': [], 'duties': [], 'structure': {}}
        
        logger.info(f"Parsing table with {len(table_data)} rows")
        
        # Clean the table data
        cleaned_table = self._clean_table(table_data)
        logger.info(f"Cleaned table: {len(cleaned_table)} rows")
        
        if not cleaned_table:
            return {'headers': [], 'faculty_rows': [], 'duties': [], 'structure': {}}
        
        # Try to detect structure first
        structure = self._detect_structure(cleaned_table)
        logger.info(f"Table structure: {structure}")
        
        # Extract headers
        headers = self._extract_headers(cleaned_table, structure)
        logger.info(f"Headers: {headers}")
        
        # Extract faculty rows
        faculty_rows = self._extract_faculty_rows(cleaned_table, structure)
        logger.info(f"Faculty rows: {len(faculty_rows)}")
        
        # Map checkmarks to duties
        duties = self._map_checkmarks_to_duties(faculty_rows, headers, structure)
        logger.info(f"Extracted {len(duties)} duties from table structure")
        
        # If no duties found, try alternative parsing with raw text
        if not duties:
            logger.warning("No duties found from table structure, trying alternative parsing...")
            
            if raw_text:
                full_text = raw_text
                logger.info(f"Using raw text with {len(full_text)} characters")
            else:
                all_text = []
                for row in cleaned_table:
                    row_text = " ".join(str(cell) for cell in row if cell)
                    if row_text.strip():
                        all_text.append(row_text)
                full_text = " ".join(all_text)
                logger.info(f"Using flattened table text with {len(full_text)} characters")
            
            duties = self._parse_text_directly(full_text, valid_dates)
            logger.info(f"Alternative parsing extracted {len(duties)} duties")
        
        return {
            'headers': headers,
            'faculty_rows': faculty_rows,
            'duties': duties,
            'structure': structure
        }
    
    def _clean_table(self, table: List[List[str]]) -> List[List[str]]:
        """Clean and normalize table data."""
        cleaned = []
        for row in table:
            if row:
                cleaned_row = [
                    str(cell).strip() if cell else "" 
                    for cell in row
                ]
                if any(cleaned_row):
                    cleaned.append(cleaned_row)
        return cleaned
    
    def _detect_structure(self, table: List[List[str]]) -> Dict[str, Any]:
        """Detect table structure with improved logic."""
        if not table:
            return {'rows': 0, 'cols': 0, 'header_row': -1, 'is_valid': True}
        
        rows = len(table)
        cols = len(table[0]) if table else 0
        
        # Patterns for detecting headers
        date_pattern = r'\d{1,2}\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        name_pattern = r'Name|Staff|Faculty|Lecturer'
        checkmark_pattern = r'[✓✔✅]'
        
        header_row = 0
        found_headers = False
        
        for i, row in enumerate(table):
            row_text = " ".join(str(cell) for cell in row)
            
            # Check if this row looks like a real header
            has_dates = bool(re.search(date_pattern, row_text))
            has_names = bool(re.search(name_pattern, row_text, re.IGNORECASE))
            has_checkmarks = bool(re.search(checkmark_pattern, row_text))
            
            # A header row should have dates/names and NO checkmarks
            if (has_dates or has_names) and not has_checkmarks:
                header_row = i
                found_headers = True
                break
        
        # If no header found, try to find any row with content
        if not found_headers:
            for i, row in enumerate(table):
                row_text = " ".join(str(cell) for cell in row if cell)
                if len(row_text) > 10 and re.search(r'[A-Za-z]', row_text):
                    header_row = i
                    found_headers = True
                    break
        
        return {
            'rows': rows,
            'cols': cols,
            'header_row': header_row,
            'is_valid': True
        }
    
    def _extract_headers(self, table: List[List[str]], structure: Dict) -> List[str]:
        """Extract header information from table."""
        header_row_idx = structure.get('header_row', 0)
        
        if header_row_idx < 0 or header_row_idx >= len(table):
            return []
        
        return [str(cell).strip() for cell in table[header_row_idx]]
    
    def _extract_faculty_rows(self, table: List[List[str]], structure: Dict) -> List[Dict]:
        """Extract faculty rows from table with better detection."""
        header_row = structure.get('header_row', 0)
        faculty_rows = []
        
        for i, row in enumerate(table):
            if i <= header_row:
                continue
            
            if not any(row):
                continue
            
            # Combine all cells to check if this is a faculty row
            row_text = " ".join(str(cell) for cell in row if cell)
            
            # Check if row contains a name (capital letters, length > 2)
            name_pattern = r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*'
            names = re.findall(name_pattern, row_text)
            
            # Check if row contains a checkmark
            has_checkmark = bool(re.search(r'[✓✔✅]', row_text))
            
            # Skip rows that are just dates or numbers
            if not names and not has_checkmark:
                continue
            
            # Find the faculty name
            faculty_name = None
            
            # Check first cell
            if row and len(row) > 0:
                cell = str(row[0]).strip()
                if cell and len(cell) > 2 and not self.checkmark_detector.detect(cell):
                    if re.search(r'[A-Za-z]', cell):
                        faculty_name = cell
            
            # If not found, try to find name in any cell
            if not faculty_name:
                for cell in row:
                    cell_str = str(cell).strip()
                    if cell_str and len(cell_str) > 2:
                        if re.search(r'[A-Z][a-z]', cell_str) and not self.checkmark_detector.detect(cell_str):
                            faculty_name = cell_str
                            break
            
            # If still not found, use the first name from regex
            if not faculty_name and names:
                faculty_name = names[0]
            
            if faculty_name:
                faculty_rows.append({
                    'row_index': i,
                    'faculty_name': faculty_name,
                    'cells': [str(cell).strip() for cell in row[1:]] if len(row) > 1 else []
                })
        
        return faculty_rows
    
    def _map_checkmarks_to_duties(
        self, 
        faculty_rows: List[Dict], 
        headers: List[str], 
        structure: Dict
    ) -> List[Dict]:
        """Map checkmarks in table cells to duties."""
        duties = []
        
        if not faculty_rows:
            logger.warning("No faculty rows found")
            return duties
        
        logger.info(f"Mapping checkmarks for {len(faculty_rows)} faculty rows")
        
        for faculty_row in faculty_rows:
            faculty_name = faculty_row['faculty_name']
            cells = faculty_row['cells']
            
            logger.info(f"Processing faculty: {faculty_name}, cells: {len(cells)}")
            
            for cell_idx, cell in enumerate(cells):
                # Check if cell contains a checkmark
                has_checkmark = self.checkmark_detector.detect(cell)
                
                if has_checkmark:
                    # Extract date/time from header
                    header_idx = cell_idx
                    if header_idx < len(headers):
                        header_text = headers[header_idx]
                        logger.info(f"Checkmark found for {faculty_name} at header: {header_text}")
                        
                        # Extract entities from header and cell combined
                        combined_text = f"{header_text} {cell}"
                        entities = self.entity_mapper.extract_entities(combined_text)
                        
                        if not entities.get('date'):
                            entities = self.entity_mapper.extract_entities(cell)
                        
                        duty = {
                            'faculty_name': faculty_name,
                            'date': entities.get('date'),
                            'time': entities.get('time'),
                            'venue': entities.get('venue'),
                            'exam_name': entities.get('exam_name') or 'Exam Duty',
                            'raw_header': header_text,
                            'cell_content': cell,
                            'faculty_names': [faculty_name]
                        }
                        duties.append(duty)
        
        return duties
    
    def _parse_text_directly(self, text: str, valid_dates: List[str] = None) -> List[Dict]:
        """Parse text directly by extracting table rows with faculty names and checkmarks."""
        duties = []
        
        if not text or len(text.strip()) < 10:
            return duties
        
        logger.info(f"Direct text parsing for {len(text)} characters")
        
        # ============================================
        # STEP 1: Extract all dates AND time indicators
        # ============================================
        date_pattern = r'(\d{1,2}-[A-Za-z]{3})'
        all_dates = re.findall(date_pattern, text)
        
        unique_dates = []
        for d in all_dates:
            if d not in unique_dates:
                unique_dates.append(d)
        
        logger.info(f"Found {len(unique_dates)} unique dates: {unique_dates[:10]}")
        
        # Extract time indicators (M/A) from the header
        lines = text.split('\n')
        time_indicators = []
        
        for line in lines:
            if re.search(r'[|]\s*[MA]\s*[|]', line) or re.search(r'\s+[MA]\s+[MA]', line):
                indicators = re.findall(r'[MA]', line)
                if len(indicators) >= len(unique_dates):
                    time_indicators = indicators
                    logger.info(f"Found time indicators: {time_indicators[:10]}")
                    break
        
        if valid_dates and len(valid_dates) > 0:
            if len(valid_dates) >= len(unique_dates):
                unique_dates = valid_dates
        
        # ============================================
        # STEP 2: Find table rows with faculty names and checkmarks
        # ============================================
        name_pattern = r'(Dr\.?\s*[A-Z][a-z]+\s+[A-Z]\.?|Mr\.?\s*[A-Z][a-z]+\s+[A-Z]\.?|Ms\.?\s*[A-Z][a-z]+\s+[A-Z]\.?|Prof\.?\s*[A-Z][a-z]+\s+[A-Z]\.?|[A-Z][a-z]+\s+[A-Z]\.?)'
        checkmark_pattern = r'[✓✔✅]'
        
        faculty_duties = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            name_match = re.search(name_pattern, line)
            if name_match:
                faculty_name = name_match.group(1).strip()
                
                skip_words = ['Name', 'Staff', 'The', 'Of', 'And', 'For', 'With', 'Page', 'Total']
                if faculty_name in skip_words:
                    continue
                
                cells = [cell.strip() for cell in line.split('|')]
                
                name_index = -1
                for i, cell in enumerate(cells):
                    if faculty_name in cell:
                        name_index = i
                        break
                
                if name_index != -1:
                    duty_cells = cells[name_index + 1:]
                    
                    for i, cell in enumerate(duty_cells):
                        if i < len(unique_dates):
                            date = unique_dates[i]
                            time_indicator = None
                            if i < len(time_indicators):
                                time_indicator = time_indicators[i]
                            
                            if re.search(checkmark_pattern, cell):
                                logger.info(f"✅ {faculty_name} has duty on {date} ({time_indicator})")
                                faculty_duties.append({
                                    'faculty_name': faculty_name,
                                    'date': date,
                                    'time': time_indicator,
                                })
        
        # ============================================
        # STEP 3: Create duties from extracted data
        # ============================================
        for fd in faculty_duties:
            if not any(d['faculty_name'] == fd['faculty_name'] and d.get('date') == fd['date'] for d in duties):
                duties.append({
                    'faculty_name': fd['faculty_name'],
                    'date': fd['date'],
                    'time': fd.get('time'),
                    'venue': None,
                    'exam_name': 'Exam Duty',
                    'faculty_names': [fd['faculty_name']]
                })
        
        # ============================================
        # STEP 4: If no duties found, try GLiNER
        # ============================================
        if not duties:
            logger.info("No duties found from table rows, trying GLiNER fallback...")
            entities = self.entity_mapper.extract_entities(text)
            faculty_names = entities.get('faculty_names', [])
            
            logger.info(f"GLiNER found {len(faculty_names)} faculty names: {faculty_names[:5]}")
            
            if faculty_names and unique_dates:
                for name in faculty_names:
                    name_clean = name.strip()
                    if len(name_clean) >= 3:
                        for line in lines:
                            if name_clean in line:
                                if re.search(checkmark_pattern, line):
                                    cells = [cell.strip() for cell in line.split('|')]
                                    for i, cell in enumerate(cells):
                                        if i < len(unique_dates) and re.search(checkmark_pattern, cell):
                                            date = unique_dates[i]
                                            time_indicator = None
                                            if i < len(time_indicators):
                                                time_indicator = time_indicators[i]
                                            if not any(d['faculty_name'] == name_clean and d.get('date') == date for d in duties):
                                                duties.append({
                                                    'faculty_name': name_clean,
                                                    'date': date,
                                                    'time': time_indicator,
                                                    'venue': None,
                                                    'exam_name': 'Exam Duty',
                                                    'faculty_names': [name_clean]
                                                })
        
        logger.info(f"Direct text parsing found {len(duties)} duties")
        return duties
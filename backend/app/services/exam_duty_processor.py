"""
Exam Duty Processor

This module orchestrates the entire exam duty extraction process:
1. Determines parser type from file
2. Parses the file
3. Extracts entities and checkmarks
4. Creates duty records
5. Triggers reminders and notifications
"""

import os
import re
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.exam_duty_parser import (
    ParserFactory,
    TableParser,
    CheckmarkDetector,
    EntityMapper,
    DutyCreator
)
from app.services.duty_scheduler import DutyScheduler
from app.services.duty_matcher import DutyMatcher
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


class ExamDutyProcessor:
    """
    Orchestrates exam duty extraction and creation.
    
    Flow:
    1. File → Parser
    2. Parser → Raw Data
    3. Raw Data → Tables/Text
    4. Tables → Checkmarks + Entities
    5. Checkmarks + Entities → Duties
    6. Duties → Database
    7. Duties → Reminders
    """
    
    def __init__(self, db: Optional[Session] = None):
        """
        Initialize processor with database session.
        
        Args:
            db: SQLAlchemy session (creates new if not provided)
        """
        self.db = db or SessionLocal()
        self._should_close_db = db is None
        
        # Initialize components
        self.table_parser = TableParser()
        self.checkmark_detector = CheckmarkDetector()
        self.entity_mapper = EntityMapper()
        self.duty_creator = DutyCreator(self.db)
        self.duty_scheduler = DutyScheduler()
        self.duty_matcher = DutyMatcher()
    
    def process(self, file_path: str, hod_id: int) -> Dict[str, Any]:
        """
        Process an exam duty file and create duty records.
        
        Args:
            file_path: Path to the file
            hod_id: ID of the HOD uploading the schedule
            
        Returns:
            Dict with processing results
        """
        try:
            logger.info(f"Starting processing for: {file_path}")
            
            # Step 1: Get parser
            parser = ParserFactory.get_parser(file_path)
            if not parser:
                return {
                    'success': False,
                    'created': 0,
                    'skipped': 0,
                    'conflicts': [],
                    'errors': ['Unsupported file type'],
                    'message': 'File type not supported'
                }
            
            # Step 2: Parse file
            logger.info("Parsing file...")
            parsed_data = parser.parse()
            logger.info(f"Parsed data keys: {list(parsed_data.keys()) if parsed_data else 'None'}")
            
            if not parsed_data:
                return {
                    'success': False,
                    'created': 0,
                    'skipped': 0,
                    'conflicts': [],
                    'errors': ['Failed to parse file'],
                    'message': 'Could not extract data from file'
                }
            
            raw_text = parsed_data.get('raw_text', '')
            logger.info(f"Raw text length: {len(raw_text)} characters")
            
            if not raw_text or len(raw_text.strip()) < 10:
                return {
                    'success': False,
                    'created': 0,
                    'skipped': 0,
                    'conflicts': [],
                    'errors': ['No text extracted from file'],
                    'message': 'Could not extract text from file'
                }
            
            # Step 3: Extract valid dates from parsed data
            valid_dates = self._extract_valid_dates(parsed_data)
            logger.info(f"Valid dates: {valid_dates[:10] if valid_dates else 'none'}")
            
            # Step 4: Process tables
            duties = []
            tables = parsed_data.get('tables', [])
            
            if tables:
                logger.info(f"Found {len(tables)} tables")
                for table_data in tables:
                    try:
                        logger.info(f"Processing table with {len(table_data)} rows")
                        table_result = self.table_parser.parse_table(
                            table_data, 
                            raw_text=raw_text,
                            valid_dates=valid_dates
                        )
                        duties.extend(table_result.get('duties', []))
                        logger.info(f"Extracted {len(table_result.get('duties', []))} duties from table")
                    except Exception as e:
                        logger.error(f"Error processing table: {str(e)}")
                        continue
            
            # Step 5: Process raw text directly
            if raw_text:
                try:
                    logger.info("Processing raw text for duties...")
                    text_duties = self._process_text(raw_text, valid_dates)
                    logger.info(f"Extracted {len(text_duties)} duties from raw text")
                    duties.extend(text_duties)
                except Exception as e:
                    logger.error(f"Error processing raw text: {str(e)}")
            
            # Step 6: Remove duplicates
            duties = self._deduplicate_duties(duties)
            logger.info(f"Total unique duties: {len(duties)}")
            
            if not duties:
                return {
                    'success': False,
                    'created': 0,
                    'skipped': 0,
                    'conflicts': [],
                    'errors': ['No duties found in file'],
                    'message': 'No duties could be extracted from the file'
                }
            
            # Step 7: Get department from HOD
            from app.models.user import User
            hod = self.db.query(User).filter(User.id == hod_id).first()
            department = hod.department if hod else 'CSE'
            logger.info(f"Department: {department}")
            
            # Step 8: Match with lecturers
            try:
                logger.info("Matching lecturers...")
                matched, unmatched = self.duty_matcher.match_lecturers(
                    duties,
                    department,
                    self.db
                )
                logger.info(f"Matched: {len(matched)}, Unmatched: {len(unmatched)}")
            except Exception as e:
                logger.error(f"Error matching lecturers: {str(e)}")
                return {
                    'success': False,
                    'created': 0,
                    'skipped': 0,
                    'conflicts': [],
                    'errors': [f'Error matching lecturers: {str(e)}'],
                    'message': f'Error matching lecturers: {str(e)}'
                }
            
            if not matched:
                return {
                    'success': False,
                    'created': 0,
                    'skipped': 0,
                    'conflicts': [],
                    'errors': ['No lecturers could be matched'],
                    'message': 'No lecturers found in database',
                    'unmatched': unmatched
                }
            
            # Step 9: Create duties
            try:
                logger.info("Creating duties...")
                result = self.duty_creator.create_duties(matched, hod_id, valid_dates)
                logger.info(f"Created: {result['created']}, Skipped: {result['skipped']}")
            except Exception as e:
                logger.error(f"Error creating duties: {str(e)}")
                return {
                    'success': False,
                    'created': 0,
                    'skipped': 0,
                    'conflicts': [],
                    'errors': [f'Error creating duties: {str(e)}'],
                    'message': f'Error creating duties: {str(e)}'
                }
            
            # Step 10: Schedule reminders
            if result['created'] > 0:
                try:
                    logger.info("Scheduling reminders...")
                    scheduled = self.duty_scheduler.schedule_reminders_for_new_duties(self.db)
                    logger.info(f"Scheduled {scheduled} reminders")
                except Exception as e:
                    logger.error(f"Failed to schedule reminders: {str(e)}")
            
            return {
                'success': True,
                'created': result['created'],
                'skipped': result['skipped'],
                'conflicts': result['conflicts'],
                'errors': result['errors'],
                'unmatched': unmatched,
                'message': f"Created {result['created']} duties, skipped {result['skipped']}"
            }
            
        except Exception as e:
            logger.error(f"Error processing exam duty file: {str(e)}", exc_info=True)
            return {
                'success': False,
                'created': 0,
                'skipped': 0,
                'conflicts': [],
                'errors': [str(e)],
                'message': f'Processing failed: {str(e)}'
            }
        finally:
            if self._should_close_db:
                self.db.close()
    
    def _extract_valid_dates(self, parsed_data: Dict) -> List[str]:
        """Extract valid dates from the parsed data."""
        valid_dates = []
        
        # Try to extract from raw text
        raw_text = parsed_data.get('raw_text', '')
        if raw_text:
            date_pattern = r'(\d{1,2}-[A-Za-z]{3})'
            dates = re.findall(date_pattern, raw_text)
            for d in dates:
                if d not in valid_dates:
                    valid_dates.append(d)
        
        # Try to extract from tables
        tables = parsed_data.get('tables', [])
        for table in tables:
            if table:
                if isinstance(table, list) and len(table) > 0:
                    first_row = table[0]
                    if isinstance(first_row, list):
                        for cell in first_row:
                            cell_str = str(cell).strip()
                            match = re.search(r'(\d{1,2}-[A-Za-z]{3})', cell_str)
                            if match:
                                date = match.group(1)
                                if date not in valid_dates:
                                    valid_dates.append(date)
                elif isinstance(table, dict) and 'rows' in table:
                    rows = table.get('rows', [])
                    if rows and len(rows) > 0:
                        first_row = rows[0]
                        if isinstance(first_row, list):
                            for cell in first_row:
                                cell_str = str(cell).strip()
                                match = re.search(r'(\d{1,2}-[A-Za-z]{3})', cell_str)
                                if match:
                                    date = match.group(1)
                                    if date not in valid_dates:
                                        valid_dates.append(date)
        
        return valid_dates
    
    def _process_text(self, text: str, valid_dates: List[str] = None) -> list:
        """Process raw text to find duties."""
        duties = []
        
        if not text or len(text.strip()) < 3:
            return duties
        
        lines = text.split('\n')
        
        for line in lines:
            if not line.strip():
                continue
            
            try:
                entities = self.entity_mapper.extract_entities(line)
                
                if entities.get('faculty_names') and entities.get('date'):
                    for faculty in entities['faculty_names']:
                        date_str = entities.get('date')
                        if valid_dates:
                            validated_date = self._validate_date_with_list(date_str, valid_dates)
                            if validated_date:
                                date_str = validated_date.strftime('%d-%b')
                        duty = {
                            'faculty_name': faculty,
                            'date': date_str,
                            'time': entities.get('time'),
                            'venue': entities.get('venue'),
                            'exam_name': entities.get('exam_name'),
                            'raw_text': line
                        }
                        duties.append(duty)
            except Exception as e:
                logger.error(f"Error processing line: {line[:50]}... Error: {str(e)}")
                continue
        
        return duties
    
    def _validate_date_with_list(self, date_str: str, valid_dates: List[str]):
        """Validate date against valid dates list."""
        from datetime import datetime, date
        try:
            from dateparser import parse
            parsed = parse(date_str)
            if parsed:
                formatted = parsed.strftime('%d-%b')
                formatted = formatted.lstrip('0')
                if formatted in valid_dates:
                    return parsed.date()
                for valid_date in valid_dates:
                    valid_parsed = parse(valid_date)
                    if valid_parsed:
                        if abs((parsed.date() - valid_parsed.date()).days) <= 3:
                            return valid_parsed.date()
        except Exception:
            pass
        return None
    
    def _deduplicate_duties(self, duties: list) -> list:
        """Remove duplicate duties."""
        seen = set()
        unique = []
        
        for duty in duties:
            key = f"{duty.get('faculty_name', '')}_{duty.get('date', '')}_{duty.get('time', '')}"
            if key not in seen:
                seen.add(key)
                unique.append(duty)
        
        return unique
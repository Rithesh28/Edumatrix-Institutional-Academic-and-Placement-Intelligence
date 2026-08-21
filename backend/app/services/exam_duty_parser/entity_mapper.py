"""
Entity Mapper for Exam Duty Extraction

This module extracts and maps entities from text:
- Faculty names (using GLiNER with regex fallback)
- Dates (using dateparser)
- Times (using regex)
- Venues (using GLiNER with regex fallback)
- Exam names (using GLiNER with regex fallback)

It then maps checkmarks to these entities to create duty assignments.
"""

from typing import Dict, List, Any, Optional, Tuple
import re
from datetime import datetime, date, time
try:
    import dateparser
    DATEPARSER_AVAILABLE = True
except ImportError:
    dateparser = None
    DATEPARSER_AVAILABLE = False
import logging

logger = logging.getLogger(__name__)

# Global GLiNER instance (load once)
_gliner_model = None
_gliner_loaded = False


def get_gliner_model():
    """Get GLiNER model instance (disabled for fast local execution)."""
    global _gliner_model, _gliner_loaded
    _gliner_loaded = True
    return None


class EntityMapper:
    """
    Maps entities extracted from text to structured duty assignments.
    
    Features:
    - Extracts faculty names using GLiNER (falls back to regex)
    - Extracts dates using dateparser
    - Extracts times using regex
    - Extracts venues using GLiNER (falls back to regex)
    - Extracts exam names using GLiNER (falls back to regex)
    - Maps checkmarks to duties
    """
    
    def __init__(self):
        """Initialize entity mapper."""
        self._gliner_model = get_gliner_model()
    
    def extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract entities from text.
        
        Args:
            text: Text to extract entities from
            
        Returns:
            Dict with extracted entities:
            {
                'faculty_names': List[str],
                'date': Optional[str],
                'time': Optional[str],
                'venue': Optional[str],
                'exam_name': Optional[str],
                'raw_text': str
            }
        """
        if not text or len(text.strip()) < 3:
            return {
                'faculty_names': [],
                'date': None,
                'time': None,
                'venue': None,
                'exam_name': None,
                'raw_text': text
            }
        
        result = {
            'faculty_names': [],
            'date': None,
            'time': None,
            'venue': None,
            'exam_name': None,
            'raw_text': text
        }
        
        try:
            # Extract date
            date_result = self._extract_date(text)
            if date_result:
                result['date'] = date_result
            
            # Extract time
            time_result = self._extract_time(text)
            if time_result:
                result['time'] = time_result
            
            # Extract faculty names using GLiNER (with fallback)
            faculty_names = self._extract_faculty_names(text)
            if faculty_names:
                result['faculty_names'] = faculty_names
            
            # Extract venue using GLiNER (with fallback)
            venue = self._extract_venue(text)
            if venue:
                result['venue'] = venue
            
            # Extract exam name using GLiNER (with fallback)
            exam_name = self._extract_exam_name(text)
            if exam_name:
                result['exam_name'] = exam_name
                
        except Exception as e:
            logger.error(f"Error extracting entities: {str(e)}")
        
        return result
    
    def _extract_date(self, text: str) -> Optional[str]:
        """
        Extract date from text using dateparser and regex.
        
        Args:
            text: Text to extract date from
            
        Returns:
            Date string in YYYY-MM-DD format or None
        """
        try:
            # Try dateparser first
            parsed = dateparser.parse(text, settings={'STRICT_PARSING': False})
            if parsed:
                return parsed.strftime('%Y-%m-%d')
        except Exception:
            pass
        
        # Try regex patterns
        patterns = [
            # DD Month YYYY or DD Month YY
            r'(\d{1,2}\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*\d{2,4})',
            # DD/MM/YYYY or DD-MM-YYYY
            r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            # DD MonthName YYYY
            r'(\d{1,2}\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s*\d{2,4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_time(self, text: str) -> Optional[str]:
        """
        Extract time from text using regex.
        
        Args:
            text: Text to extract time from
            
        Returns:
            Time string or None
        """
        patterns = [
            # HH:MM AM/PM
            r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)',
            # HH AM/PM
            r'(\d{1,2}\s*(?:AM|PM|am|pm))',
            # Morning/Afternoon/Evening
            r'(morning|afternoon|evening|Morning|Afternoon|Evening)',
            # 9AM, 10PM format
            r'(\d{1,2}\s*(?:AM|PM|am|pm))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_faculty_names(self, text: str) -> List[str]:
        """
        Extract faculty names using GLiNER with regex fallback.
        
        Args:
            text: Text to extract names from
            
        Returns:
            List of faculty names
        """
        # Try GLiNER first
        if self._gliner_model:
            try:
                labels = ['Person', 'Faculty', 'Professor', 'Dr', 'Doctor']
                entities = self._gliner_model.predict_entities(text, labels)
                
                names = []
                for entity in entities:
                    if entity['label'] in labels and entity['score'] > 0.5:
                        names.append(entity['text'])
                
                if names:
                    return names
            except Exception as e:
                logger.debug(f"GLiNER name extraction failed: {str(e)}")
        
        # Fallback to regex
        return self._extract_names_regex(text)
    
    def _extract_names_regex(self, text: str) -> List[str]:
        """
        Extract names using regex patterns (fallback).
        
        Args:
            text: Text to extract names from
            
        Returns:
            List of names
        """
        names = []
        
        # Patterns for faculty names
        patterns = [
            # Dr. Name or Dr Name
            r'(?:Dr\.?|Prof\.?|Professor)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            # Name (Dr.) or Name (Prof.)
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+\((?:Dr\.?|Prof\.?|Professor)\)',
            # Name, Dr.
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*(?:Dr\.?|Prof\.?|Professor)',
            # Just a name with title-like prefix
            r'(?:Dr|Prof|Professor|Mr|Mrs|Ms|Er)\s*\.?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            names.extend(matches)
        
        # Remove duplicates
        unique_names = []
        seen = set()
        for name in names:
            name_lower = name.lower()
            if name_lower not in seen:
                seen.add(name_lower)
                unique_names.append(name)
        
        return unique_names
    
    def _extract_venue(self, text: str) -> Optional[str]:
        """
        Extract venue using GLiNER with regex fallback.
        
        Args:
            text: Text to extract venue from
            
        Returns:
            Venue string or None
        """
        # Try GLiNER first
        if self._gliner_model:
            try:
                labels = ['Location', 'Venue', 'Room', 'Hall', 'Auditorium']
                entities = self._gliner_model.predict_entities(text, labels)
                
                for entity in entities:
                    if entity['label'] in labels and entity['score'] > 0.5:
                        return entity['text']
            except Exception:
                pass
        
        # Fallback to regex
        return self._extract_venue_regex(text)
    
    def _extract_venue_regex(self, text: str) -> Optional[str]:
        """
        Extract venue using regex patterns (fallback).
        
        Args:
            text: Text to extract venue from
            
        Returns:
            Venue string or None
        """
        patterns = [
            r'(?:Venue|Room|Hall|Auditorium|Location):\s*([^\n,]+)',
            r'(?:in|at)\s+([A-Z][a-z]+\s+(?:Hall|Room|Auditorium|Block|Floor))',
            r'([A-Z][a-z]+\s+(?:Hall|Room|Auditorium))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_exam_name(self, text: str) -> Optional[str]:
        """
        Extract exam name using GLiNER with regex fallback.
        
        Args:
            text: Text to extract exam name from
            
        Returns:
            Exam name or None
        """
        # Try GLiNER first
        if self._gliner_model:
            try:
                labels = ['Exam', 'Subject', 'Course', 'Test']
                entities = self._gliner_model.predict_entities(text, labels)
                
                for entity in entities:
                    if entity['label'] in labels and entity['score'] > 0.5:
                        return entity['text']
            except Exception:
                pass
        
        # Fallback to regex
        return self._extract_exam_name_regex(text)
    
    def _extract_exam_name_regex(self, text: str) -> Optional[str]:
        """
        Extract exam name using regex patterns (fallback).
        
        Args:
            text: Text to extract exam name from
            
        Returns:
            Exam name or None
        """
        patterns = [
            # Exam: Name
            r'(?:Exam|Test|Paper|Quiz|Examination):\s*([^\n,]+)',
            # Name Exam
            r'([A-Z]{2,}[A-Z\s]*)\s*(?:Exam|Test|Paper)',
            # Exam Name in uppercase
            r'([A-Z]{2,}(?:\s+[A-Z]{2,})*)\s*(?:Exam|Test)?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def map_checkmarks_to_duties(
        self, 
        checkmarks: List[Dict], 
        entities: List[Dict]
    ) -> List[Dict]:
        """
        Map checkmarks to entities to create duty assignments.
        
        Args:
            checkmarks: List of checkmark dictionaries
            entities: List of entity dictionaries
            
        Returns:
            List of duty assignments
        """
        duties = []
        
        for checkmark in checkmarks:
            position = checkmark.get('position', -1)
            context = checkmark.get('context', '')
            
            for entity in entities:
                entity_text = entity.get('raw_text', '')
                if entity_text and entity_text in context:
                    duties.append({
                        'faculty_names': entity.get('faculty_names', []),
                        'date': entity.get('date'),
                        'time': entity.get('time'),
                        'venue': entity.get('venue'),
                        'exam_name': entity.get('exam_name'),
                        'checkmark': checkmark
                    })
                    break
        
        return duties
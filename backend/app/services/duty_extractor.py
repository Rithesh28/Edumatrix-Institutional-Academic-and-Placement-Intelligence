import re
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DutyExtractor:
    """Extract exam duty information from text"""
    
    def extract_duties(self, text: str) -> List[Dict[str, Any]]:
        """Extract duty details from text with universal pattern support."""
        if not text or len(text.strip()) < 5:
            return []
        
        duties = []
        raw_lines = text.split('\n')
        
        # Month map
        month_map = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06','jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}
        
        for raw_line in raw_lines:
            line = raw_line.strip()
            if len(line) < 5:
                continue
            
            # Skip pure headers
            line_lower = line.lower()
            if sum(1 for kw in ['sl.no', 'faculty name', 'staff name', 'invigilator', 'signature', 'date of exam'] if kw in line_lower) >= 2:
                continue
            
            # 1. Date Detection
            date_match = re.search(r'(\b\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}\b|\b\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*-\d{2,4}\b|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\b)', line, re.IGNORECASE)
            
            # 2. Session Detection
            session_match = re.search(r'(\b(?:FN|AN|FORENOON|AFTERNOON|MORNING|EVENING)\b|\b\d{1,2}:\d{2}\s*(?:AM|PM)?\s*[-–toTO]+\s*\d{1,2}:\d{2}\s*(?:AM|PM)?\b)', line, re.IGNORECASE)
            
            # 3. Venue Detection
            venue_match = re.search(r'\b(Hall\s*[-#]?\s*\d+|Room\s*[-#]?\s*\d+|LH\s*[-#]?\s*\d+|Lab\s*[-#]?\s*\d+|Block\s*[A-Za-z0-9]+)\b', line, re.IGNORECASE)
            
            # 4. Faculty Extraction
            tokens = [t.strip() for t in re.split(r'\s{2,}|\t|\|', line) if t.strip()]
            faculty = ""
            
            title_match = re.search(r'(?:Dr\.|Prof\.|Mr\.|Mrs\.|Ms\.|Er\.)\s*[A-Za-z0-9_\.]+', line, re.IGNORECASE)
            if title_match:
                faculty = title_match.group(0)
            
            if not faculty and tokens:
                for tok in tokens:
                    if re.search(r'\d{1,4}[-/]\d{1,4}|\d{1,2}:\d{2}', tok):
                        continue
                    if re.search(r'\b(FN|AN|Morning|Afternoon|Hall|Room|LH|Exam|Semester|Date|Sl)\b', tok, re.IGNORECASE):
                        continue
                    if len(tok) >= 3 and not any(char.isdigit() for char in tok):
                        faculty = tok
                        break
            
            if not faculty and date_match:
                name_cand = re.sub(r'(\b\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}\b|FN|AN|Morning|Afternoon|Hall\s*\d+|Room\s*\d+|\d{1,2}:\d{2})', '', line, flags=re.IGNORECASE).strip()
                words = [w for w in re.split(r'[\|,;\s]+', name_cand) if len(w) > 2 and not w.isdigit()]
                if words:
                    faculty = ' '.join(words[:3])
            
            if faculty and date_match:
                date_str = date_match.group(0)
                time_str = session_match.group(0) if session_match else "09:30 AM"
                venue_str = venue_match.group(0) if venue_match else "Examination Hall"
                
                duty = self._parse_duty(faculty, date_str, time_str, venue_str)
                if duty:
                    duties.append(duty)
        
        logger.info(f"Extracted {len(duties)} duties from text")
        return duties
    
    def _parse_duty(self, lecturer_name: str, date_str: str, time_str: str, venue: str, end_time_str: str = None) -> Dict[str, Any]:
        """Parse individual duty details"""
        
        # Parse date
        try:
            duty_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            try:
                duty_date = datetime.strptime(date_str, "%d/%m/%Y").date()
            except ValueError:
                try:
                    duty_date = datetime.strptime(date_str, "%m/%d/%Y").date()
                except ValueError:
                    return None
        
        # Parse start time
        try:
            if "AM" in time_str or "PM" in time_str:
                start_time = datetime.strptime(time_str.strip(), "%I:%M %p").time()
            else:
                start_time = datetime.strptime(time_str.strip(), "%H:%M").time()
        except ValueError:
            try:
                start_time = datetime.strptime(time_str.strip(), "%I %p").time()
            except ValueError:
                return None
        
        # Parse end time
        end_time = None
        if end_time_str:
            try:
                if "AM" in end_time_str or "PM" in end_time_str:
                    end_time = datetime.strptime(end_time_str.strip(), "%I:%M %p").time()
                else:
                    end_time = datetime.strptime(end_time_str.strip(), "%H:%M").time()
            except ValueError:
                pass
        
        if not end_time:
            start_datetime = datetime.combine(duty_date, start_time)
            end_datetime = start_datetime + timedelta(hours=2)
            end_time = end_datetime.time()
        
        return {
            "lecturer_name": lecturer_name,
            "date": duty_date,
            "start_time": start_time,
            "end_time": end_time,
            "venue": venue,
            "exam_name": "Exam"
        }


duty_extractor = DutyExtractor()
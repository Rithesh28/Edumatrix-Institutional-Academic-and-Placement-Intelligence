from __future__ import annotations

from typing import Dict, List, Any, Optional
from datetime import datetime, date, time
try:
    from sqlalchemy.orm import Session
    from sqlalchemy import and_
    from app.models.exam_duty import ExamDuty, DutyStatus
    from app.models.duty_conflict import DutyConflict
    from app.models.user import User
    from app.core.database import SessionLocal
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    Session = Any
    and_ = None
    ExamDuty = None
    DutyStatus = None
    DutyConflict = None
    User = None
    SessionLocal = None
    SQLALCHEMY_AVAILABLE = False

import logging
import re

logger = logging.getLogger(__name__)


class DutyCreator:
    """
    Creates exam duty records from parsed data.
    """
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
        self._should_close_db = db is None
    
    def create_duties(self, duties: List[Dict[str, Any]], hod_id: int, valid_dates: List[str] = None) -> Dict[str, Any]:
        """Create exam duty records from parsed duties."""
        result = {
            'created': 0,
            'skipped': 0,
            'conflicts': [],
            'errors': []
        }
        
        today = date.today()
        
        for duty_data in duties:
            try:
                faculty_name = duty_data.get('faculty_name')
                date_str = duty_data.get('date')
                time_indicator = duty_data.get('time')
                logger.info(f"Processing: '{faculty_name}' on '{date_str}' (Time: {time_indicator})")
                
                # Get lecturer ID
                lecturer_id = self._get_lecturer_id(faculty_name)
                if not lecturer_id:
                    result['errors'].append(f"Lecturer not found: {faculty_name}")
                    continue
                
                # Parse and validate date
                duty_date = self._parse_date(date_str)
                if not duty_date:
                    result['errors'].append(f"Invalid date: {date_str}")
                    continue
                
                # SKIP PAST DUTIES
                if duty_date < today:
                    logger.info(f"⏭️ Skipping past duty: {faculty_name} on {duty_date}")
                    result['skipped'] += 1
                    continue
                
                # Validate date against valid dates if provided
                if valid_dates:
                    validated_date = self._validate_date_with_list(date_str, valid_dates)
                    if validated_date:
                        duty_date = validated_date
                        logger.info(f"📝 Validated date: '{date_str}' → '{duty_date.strftime('%d-%b')}'")
                    else:
                        closest = self._find_closest_date(date_str, valid_dates)
                        if closest:
                            duty_date = self._parse_date(closest)
                            if duty_date:
                                logger.info(f"📝 Corrected date: '{date_str}' → '{closest}'")
                
                # Parse time from M/A indicator
                start_time, end_time = self._parse_time_from_indicator(time_indicator)
                if not start_time:
                    start_time = time(9, 0)
                    end_time = time(12, 0)
                
                # Check for duplicate
                existing = self._check_duplicate(
                    lecturer_id, duty_date, start_time, duty_data.get('exam_name')
                )
                if existing:
                    result['skipped'] += 1
                    logger.info(f"⏭️ Skipped duplicate: {faculty_name} on {duty_date}")
                    continue
                
                # Check for conflict
                conflict = self._check_conflict(lecturer_id, duty_date, start_time)
                if conflict:
                    result['conflicts'].append({
                        'lecturer_id': lecturer_id,
                        'lecturer_name': faculty_name,
                        'date': duty_date,
                        'time': duty_data.get('time'),
                        'existing_duty': conflict
                    })
                    logger.warning(f"⚠️ Conflict detected for {faculty_name} on {duty_date}")
                
                # Create duty record - venue removed
                exam_duty = ExamDuty(
                    lecturer_id=lecturer_id,
                    hod_id=hod_id,
                    department=self._get_department(lecturer_id),
                    exam_name=duty_data.get('exam_name', 'Exam Duty'),
                    date=duty_date,
                    start_time=start_time,
                    end_time=end_time or self._calculate_end_time(start_time),
                    # venue=venue,  # ← REMOVED
                    status=DutyStatus.PENDING
                )
                
                self.db.add(exam_duty)
                result['created'] += 1
                logger.info(f"✅ Created duty for {faculty_name} on {duty_date} at {start_time}")
                
            except Exception as e:
                result['errors'].append(f"Error creating duty: {str(e)}")
                logger.error(f"Error creating duty: {str(e)}")
        
        # Commit all changes
        try:
            self.db.commit()
            logger.info(f"Committed {result['created']} duties to database")
        except Exception as e:
            self.db.rollback()
            result['errors'].append(f"Database commit error: {str(e)}")
            logger.error(f"Database commit error: {str(e)}")
        
        if self._should_close_db:
            self.db.close()
        
        return result
    
    def _parse_time_from_indicator(self, time_indicator: str) -> tuple:
        """Parse time from M/A indicator."""
        if not time_indicator:
            return None, None
        
        time_indicator = time_indicator.strip().upper()
        
        if time_indicator == 'M':
            return time(9, 0), time(12, 0)
        elif time_indicator == 'A':
            return time(14, 0), time(17, 0)
        elif 'MORNING' in time_indicator:
            return time(9, 0), time(12, 0)
        elif 'AFTERNOON' in time_indicator:
            return time(14, 0), time(17, 0)
        
        return None, None
    
    def _get_lecturer_id(self, faculty_name: str) -> Optional[int]:
        """Get lecturer ID from faculty name with fuzzy matching."""
        if not faculty_name:
            logger.warning("Empty faculty name provided")
            return None
        
        name = faculty_name.strip()
        logger.info(f"Looking for lecturer: '{name}'")
        
        # Try to find by name
        user = self.db.query(User).filter(
            User.name.ilike(f"%{name}%"),
            User.role == 'lecturer'
        ).first()
        
        if user:
            logger.info(f"Found lecturer by name: {user.name} (ID: {user.id})")
            return user.id
        
        # Try cleaned name
        cleaned_name = self._clean_name(name)
        if cleaned_name != name:
            user = self.db.query(User).filter(
                User.name.ilike(f"%{cleaned_name}%"),
                User.role == 'lecturer'
            ).first()
            if user:
                logger.info(f"Found lecturer by cleaned name: {user.name} (ID: {user.id})")
                return user.id
        
        # Try fuzzy matching
        lecturers = self.db.query(User).filter(
            User.role == 'lecturer',
            User.is_active == True
        ).all()
        
        best_match = None
        best_score = 0
        
        for lecturer in lecturers:
            score = self._name_similarity(name, lecturer.name)
            if score > best_score and score > 0.4:
                best_score = score
                best_match = lecturer
        
        if best_match:
            logger.info(f"✅ Fuzzy matched '{name}' to lecturer '{best_match.name}' (score: {best_score:.2f})")
            return best_match.id
        
        logger.warning(f"No lecturer found for name: '{name}'")
        return None
    
    def _clean_name(self, name: str) -> str:
        """Clean name by removing titles and extra spaces."""
        titles = ['dr', 'prof', 'professor', 'mr', 'mrs', 'ms', 'er', 'sri', 'smt', 'doctor']
        name_lower = name.lower().strip()
        
        for title in titles:
            if name_lower.startswith(title + ' '):
                name_lower = name_lower[len(title) + 1:]
            elif name_lower.startswith(title + '.'):
                name_lower = name_lower[len(title) + 1:]
            elif name_lower.startswith(title + ','):
                name_lower = name_lower[len(title) + 1:]
        
        return ' '.join(name_lower.split())
    
    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names."""
        name1 = self._clean_name(name1).lower()
        name2 = self._clean_name(name2).lower()
        
        if not name1 or not name2:
            return 0.0
        
        if name1 == name2:
            return 1.0
        
        if name1 in name2 or name2 in name1:
            return 0.8
        
        parts1 = name1.split()
        parts2 = name2.split()
        
        common_parts = set(parts1) & set(parts2)
        if common_parts:
            return 0.7
        
        if parts1 and parts2 and parts1[0][0] == parts2[0][0]:
            if len(parts1) > 1 and len(parts2) > 1:
                if parts1[-1][0] == parts2[-1][0]:
                    return 0.6
        
        return 0.0
    
    def _find_closest_date(self, date_str: str, valid_dates: List[str]) -> Optional[str]:
        """Find the closest valid date to the given date string."""
        if not date_str or not valid_dates:
            return None
        
        try:
            import dateparser
            parsed = dateparser.parse(date_str)
            if not parsed:
                return None
            
            closest_date = None
            closest_diff = float('inf')
            
            for valid_date in valid_dates:
                valid_parsed = dateparser.parse(valid_date)
                if valid_parsed:
                    diff = abs((parsed.date() - valid_parsed.date()).days)
                    if diff < closest_diff:
                        closest_diff = diff
                        closest_date = valid_date
            
            if closest_diff <= 10:
                return closest_date
            return None
        except Exception:
            return None
    
    def _validate_date_with_list(self, date_str: str, valid_dates: List[str]) -> Optional[date]:
        """Validate date against valid dates list."""
        if not date_str or not valid_dates:
            return None
        
        try:
            import dateparser
            parsed = dateparser.parse(date_str)
            if not parsed:
                return None
            
            parsed_date = parsed.date()
            
            formatted = parsed.strftime('%d-%b')
            formatted = formatted.lstrip('0')
            if formatted in valid_dates:
                return parsed_date
            
            for valid_date in valid_dates:
                valid_parsed = dateparser.parse(valid_date)
                if valid_parsed:
                    diff = abs((parsed_date - valid_parsed.date()).days)
                    if diff <= 3:
                        return valid_parsed.date()
            
            return None
        except Exception:
            return None
    
    def _get_department(self, user_id: int) -> str:
        """Get department of a user."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if user and user.department:
            return user.department
        return "Unknown"
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        
        try:
            import dateparser
            parsed = dateparser.parse(date_str)
            if parsed:
                return parsed.date()
        except Exception:
            pass
        
        patterns = [
            r'(\d{1,2})\s*[-/]\s*([A-Za-z]{3})',
            r'(\d{1,2})\s*[-/]\s*(\d{1,2})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    day = int(match.group(1))
                    month_str = match.group(2)
                    if month_str.isdigit():
                        month = int(month_str)
                    else:
                        from datetime import datetime
                        month = datetime.strptime(month_str, '%b').month
                    year = 2026
                    return date(year, month, day)
                except Exception:
                    pass
        
        return None
    
    def _calculate_end_time(self, start_time: time) -> time:
        """Calculate end time (default 3 hours after start)."""
        from datetime import datetime, timedelta
        
        start_dt = datetime.combine(datetime.today(), start_time)
        end_dt = start_dt + timedelta(hours=3)
        return end_dt.time()
    
    def _check_duplicate(self, lecturer_id: int, duty_date: date, start_time: time, exam_name: str) -> bool:
        """Check if a duplicate duty exists."""
        existing = self.db.query(ExamDuty).filter(
            ExamDuty.lecturer_id == lecturer_id,
            ExamDuty.date == duty_date,
            ExamDuty.start_time == start_time,
            ExamDuty.exam_name == exam_name
        ).first()
        
        return existing is not None
    
    def _check_conflict(self, lecturer_id: int, duty_date: date, start_time: time) -> Optional[ExamDuty]:
        """Check if a duty conflicts with an existing duty for the same lecturer."""
        existing = self.db.query(ExamDuty).filter(
            ExamDuty.lecturer_id == lecturer_id,
            ExamDuty.date == duty_date,
            ExamDuty.start_time == start_time
        ).first()
        
        if existing:
            return existing
        
        overlapping = self.db.query(ExamDuty).filter(
            ExamDuty.lecturer_id == lecturer_id,
            ExamDuty.date == duty_date,
            ExamDuty.start_time < start_time,
            ExamDuty.end_time > start_time
        ).first()
        
        return overlapping
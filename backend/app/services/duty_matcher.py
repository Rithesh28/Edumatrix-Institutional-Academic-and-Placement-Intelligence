from sqlalchemy.orm import Session
from typing import List, Dict, Any, Tuple, Optional
from ..models.user import User, UserRole
from ..models.exam_duty import ExamDuty
import logging
import re

logger = logging.getLogger(__name__)


class DutyMatcher:
    """Match extracted lecturer names with database using fuzzy matching."""
    
    def __init__(self, db: Session = None):
        self.db = db
    
    def match_lecturers(
        self, 
        extracted_duties: List[Dict[str, Any]], 
        department: str,
        db: Session = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        
        if db is None:
            db = self.db
        
        if db is None:
            logger.error("No database session provided")
            return [], []
        
        matched = []
        unmatched = []
        
        # Get all lecturers in the department
        lecturers = db.query(User).filter(
            User.role == UserRole.LECTURER,
            User.department == department,
            User.is_active == True
        ).all()
        
        logger.info(f"Found {len(lecturers)} lecturers in department {department}")
        
        # Create name lookup with multiple variations
        name_map = {}
        for lecturer in lecturers:
            # Exact name
            name_map[lecturer.name.lower()] = lecturer
            
            # Cleaned name (remove titles)
            cleaned_name = self._clean_name(lecturer.name)
            if len(cleaned_name) > 2:
                name_map[cleaned_name.lower()] = lecturer
            
            # First + Last name
            parts = [p for p in lecturer.name.lower().split() if len(p) > 1]
            if len(parts) >= 2:
                first_last = f"{parts[0]} {parts[-1]}"
                name_map[first_last] = lecturer
                if len(parts[0]) > 3:
                    name_map[parts[0]] = lecturer
                if len(parts[-1]) > 3:
                    name_map[parts[-1]] = lecturer
        
        logger.info(f"Created name map with {len(name_map)} variations")
        
        for duty in extracted_duties:
            lecturer_name = duty.get('faculty_name', '').strip().lower()
            faculty_names = duty.get('faculty_names', [])
            
            names_to_try = []
            if lecturer_name:
                names_to_try.append(lecturer_name)
            names_to_try.extend([n.lower().strip() for n in faculty_names if n])
            names_to_try = list(set(names_to_try))
            
            matched_lecturer = None
            matched_name = None
            
            for name in names_to_try:
                if not name or len(name) < 2:
                    continue
                
                # 1. Exact match
                if name in name_map:
                    matched_lecturer = name_map[name]
                    matched_name = name
                    break
                
                # 2. Cleaned match
                cleaned = self._clean_name(name)
                if cleaned in name_map:
                    matched_lecturer = name_map[cleaned]
                    matched_name = cleaned
                    break
                
                # 3. Substring match for substantial tokens (>4 chars)
                for stored_name, lecturer in name_map.items():
                    if len(name) >= 4 and len(stored_name) >= 4:
                        if name in stored_name or stored_name in name:
                            matched_lecturer = lecturer
                            matched_name = stored_name
                            break
                
                if matched_lecturer:
                    break
            
            if matched_lecturer:
                matched_duty = duty.copy()
                matched_duty["lecturer_id"] = matched_lecturer.id
                matched_duty["lecturer_name"] = matched_lecturer.name
                matched.append(matched_duty)
                logger.info(f"✅ Matched '{matched_name}' to lecturer '{matched_lecturer.name}'")
            else:
                # 4. Try fuzzy matching
                best_match = self._fuzzy_match_name(names_to_try, name_map)
                if best_match:
                    matched_duty = duty.copy()
                    matched_duty["lecturer_id"] = best_match.id
                    matched_duty["lecturer_name"] = best_match.name
                    matched.append(matched_duty)
                    logger.info(f"✅ Fuzzy matched to lecturer '{best_match.name}'")
                else:
                    unmatched.append(lecturer_name or "Unknown")
                    logger.debug(f"❌ Unmatched name: {names_to_try}")
        
        logger.info(f"Matched {len(matched)} lecturers, {len(unmatched)} unmatched")
        return matched, unmatched
    
    def _clean_name(self, name: str) -> str:
        """Clean name by removing titles and extra spaces."""
        titles = ['dr', 'prof', 'professor', 'mr', 'mrs', 'ms', 'er', 'sri', 'smt', 'doctor']
        name_lower = name.lower().strip()
        
        for title in titles:
            if name_lower.startswith(title + ' ') or name_lower.startswith(title + '.'):
                name_lower = re.sub(rf'^{title}[\.\s]+', '', name_lower).strip()
        
        # Remove numbers and special characters
        name_lower = re.sub(r'[\d_#¥\(\)\[\]]+', '', name_lower)
        return ' '.join(name_lower.split()).strip()
    
    def _fuzzy_match_name(self, names: List[str], name_map: Dict[str, User]) -> Optional[User]:
        """Try to fuzzy match a name using sequence matcher similarity."""
        import difflib
        best_match = None
        best_score = 0.0
        
        for name in names:
            if not name or len(name) < 2:
                continue
            
            cleaned_name = self._clean_name(name)
            if not cleaned_name:
                continue
            
            for stored_name, lecturer in name_map.items():
                if len(stored_name) < 3:
                    continue
                
                # difflib similarity
                ratio = difflib.SequenceMatcher(None, cleaned_name, stored_name).ratio()
                
                # Token containment bonus
                clean_parts = [p for p in cleaned_name.split() if len(p) >= 3]
                stored_parts = [p for p in stored_name.split() if len(p) >= 3]
                common = set(clean_parts).intersection(set(stored_parts))
                if common:
                    ratio = max(ratio, 0.75 + 0.1 * len(common))
                
                # Partial suffix matching (e.g. "ishek" -> "abhishek", "vabaleshwara" -> "mahabaleshwara")
                for cp in clean_parts:
                    for sp in stored_parts:
                        if len(cp) >= 4 and len(sp) >= 4:
                            if cp in sp or sp in cp:
                                ratio = max(ratio, 0.78)
                
                if ratio > best_score and ratio >= 0.60:
                    best_score = ratio
                    best_match = lecturer
        
        return best_match
    
    def _has_common_parts(self, name1: str, name2: str) -> bool:
        """Check if two names share common parts (first name or last name)."""
        parts1 = name1.lower().split()
        parts2 = name2.lower().split()
        
        if parts1 and parts2 and parts1[0] == parts2[0]:
            return True
        
        if len(parts1) > 1 and len(parts2) > 1 and parts1[-1] == parts2[-1]:
            return True
        
        return False
    
    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names."""
        name1 = name1.lower().strip()
        name2 = name2.lower().strip()
        
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
        
        if parts1 and parts2 and parts1[0] == parts2[0]:
            if len(parts1) > 1 and len(parts2) > 1 and parts1[-1] == parts2[-1]:
                return 0.6
        
        return 0.0
    
    def detect_all_conflicts(self, db: Session = None) -> List[Dict[str, Any]]:
        """Detect all conflicts in exam duty assignments."""
        if db is None:
            db = self.db
        
        if db is None:
            return []
        
        from datetime import date
        today = date.today()
        conflicts = []
        
        duties = db.query(ExamDuty).filter(ExamDuty.date >= today).all()
        
        for duty in duties:
            overlapping = db.query(ExamDuty).filter(
                ExamDuty.lecturer_id == duty.lecturer_id,
                ExamDuty.date == duty.date,
                ExamDuty.id != duty.id,
                ExamDuty.status != 'cancelled'
            ).all()
            
            for other in overlapping:
                if duty.start_time < other.end_time and duty.end_time > other.start_time:
                    conflicts.append({
                        'duty_id': duty.id,
                        'lecturer_id': duty.lecturer_id,
                        'date': duty.date,
                        'exam_name': duty.exam_name,
                        'start_time': duty.start_time,
                        'end_time': duty.end_time,
                        'conflicting_duty_id': other.id,
                        'conflicting_exam': other.exam_name,
                        'conflict_type': 'time_overlap'
                    })
        
        return conflicts
    
    def get_conflicts_for_lecturer(self, lecturer_id: int, db: Session = None) -> List[Dict[str, Any]]:
        """Get conflicts for a specific lecturer."""
        if db is None:
            db = self.db
        
        if db is None:
            return []
        
        from datetime import date
        today = date.today()
        conflicts = []
        
        duties = db.query(ExamDuty).filter(
            ExamDuty.lecturer_id == lecturer_id,
            ExamDuty.date >= today,
            ExamDuty.status != 'cancelled'
        ).all()
        
        for i, duty in enumerate(duties):
            for other in duties[i+1:]:
                if duty.date == other.date:
                    if duty.start_time < other.end_time and duty.end_time > other.start_time:
                        conflicts.append({
                            'duty_id': duty.id,
                            'exam_name': duty.exam_name,
                            'date': duty.date,
                            'start_time': duty.start_time,
                            'end_time': duty.end_time,
                            'conflicting_duty_id': other.id,
                            'conflicting_exam': other.exam_name,
                            'conflict_type': 'time_overlap'
                        })
        
        return conflicts


duty_matcher = DutyMatcher()
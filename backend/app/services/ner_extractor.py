import os
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class NERExtractor:
    _model = None
    
    def __init__(self):
        self.model = None
        self.is_loaded = False
        # Check if GLiNER is enabled via environment variable
        self.use_gliner = os.getenv("USE_GLINER", "false").lower() == "true"
        
        if self.use_gliner:
            self._load_model()
            logger.info("✅ GLiNER enabled")
        else:
            logger.info("⚡ GLiNER disabled - using regex fallback (faster)")
    
    def _load_model(self):
        """Load GLiNER model once and cache it via shared gliner_service"""
        try:
            from app.services.gliner_service import gliner_service
            if gliner_service.is_available():
                self.model = gliner_service.get_model()
                self.is_loaded = True
                NERExtractor._model = self.model
            else:
                self.is_loaded = False
        except Exception as e:
            logger.warning(f"⚠️ GLiNER load failed: {e}")
            self.is_loaded = False
    
    def extract_entities(self, text: str, labels: list, threshold: float = 0.5):
        """Extract entities using GLiNER (if enabled)"""
        if not self.is_loaded or not self.use_gliner:
            return []
        
        try:
            return self.model.predict_entities(text, labels, threshold=threshold)
        except Exception as e:
            logger.error(f"GLiNER extraction error: {e}")
            return []
    
    def extract_dates(self, text: str):
        """Extract dates using GLiNER or regex fallback"""
        # Try GLiNER first if enabled
        if self.is_loaded and self.use_gliner:
            entities = self.extract_entities(text, ["Date", "Deadline"])
            dates = []
            for entity in entities:
                if "date" in entity["label"].lower():
                    dates.append({
                        "text": entity["text"],
                        "confidence": entity["score"],
                        "method": "gliner"
                    })
            if dates:
                return dates
        
        # Fallback: Regex (always works)
        return self._extract_dates_regex(text)
    
    def _extract_dates_regex(self, text: str):
        """Regex-based date extraction (fast fallback)"""
        dates = []
        
        # Pattern: 03 May 2026, 20 May 2026
        pattern1 = r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})\b'
        for match in re.findall(pattern1, text, re.IGNORECASE):
            dates.append({
                "text": f"{match[0]} {match[1]} {match[2]}",
                "confidence": 0.7,
                "method": "regex"
            })
        
        # Pattern: May 15, 2026
        pattern2 = r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b'
        for match in re.findall(pattern2, text, re.IGNORECASE):
            dates.append({
                "text": f"{match[0]} {match[1]}, {match[2]}",
                "confidence": 0.7,
                "method": "regex"
            })
        
        # Pattern: 2026-05-20
        pattern3 = r'\b(\d{4})-(\d{2})-(\d{2})\b'
        for match in re.findall(pattern3, text):
            dates.append({
                "text": f"{match[0]}-{match[1]}-{match[2]}",
                "confidence": 0.8,
                "method": "regex"
            })
        
        # Remove duplicates
        seen = set()
        unique = []
        for date in dates:
            if date["text"] not in seen:
                seen.add(date["text"])
                unique.append(date)
        
        return unique
    
    def extract_exam_circular_info(self, text: str):
        """Extract exam info using GLiNER (if enabled) or regex fallback"""
        result = {
            "dates": self.extract_dates(text),
            "exam_name": None,
            "venue": None,
            "subject": None,
            "deadline": None
        }
        
        # If GLiNER is enabled, try to extract extra fields
        if self.is_loaded and self.use_gliner:
            labels = ["ExamName", "EventName", "Venue", "Location", "Subject", "Deadline"]
            entities = self.extract_entities(text, labels, threshold=0.4)
            
            for entity in entities:
                label = entity["label"].lower()
                if "exam" in label or "event" in label:
                    result["exam_name"] = entity["text"]
                elif "venue" in label or "location" in label:
                    result["venue"] = entity["text"]
                elif "subject" in label:
                    result["subject"] = entity["text"]
                elif "deadline" in label:
                    result["deadline"] = entity["text"]
        
        # Always try regex for exam name (fallback)
        if not result["exam_name"]:
            exam_patterns = [
                r'(Semester|Final|Mid-term|Annual)\s+(Examination|Exam)s?',
                r'Subject:\s*(.+?)(?:\n|$)'
            ]
            for pattern in exam_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    result["exam_name"] = match.group(0).strip()
                    break
        
        return result


# Singleton instance
ner_extractor = NERExtractor()
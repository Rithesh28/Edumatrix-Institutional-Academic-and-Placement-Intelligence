"""
Date Extraction Service
Extracts dates from text using regex and NLP
"""

from datetime import datetime  # Add this at the top
import re
from datetime import datetime
from typing import List, Optional, Tuple
import logging


logger = logging.getLogger(__name__)

class DateExtractor:
    """Extract dates from text content."""
    
    # Common date patterns
    DATE_PATTERNS = [
        # DD/MM/YYYY or MM/DD/YYYY
        r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',
        # DD Month YYYY or Month DD, YYYY
        r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2,4})\b',
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{2,4}\b',
        # YYYY-MM-DD
        r'\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b',
    ]
    
    def extract_dates(self, text: str) -> List[Tuple[str, datetime]]:
        """
        Extract dates from text.
        
        Returns:
            List of (date_string, datetime_object) tuples
        """
        dates = []
        
        if not text:
            return dates
        
        for pattern in self.DATE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    dt = self._parse_date(match)
                    if dt:
                        dates.append((match, dt))
                except Exception as e:
                    logger.debug(f"Failed to parse date '{match}': {e}")
        
        # Remove duplicates
        unique_dates = []
        seen = set()
        for date_str, dt in dates:
            if dt not in seen:
                seen.add(dt)
                unique_dates.append((date_str, dt))
        
        return unique_dates
    
    def extract_future_dates(self, text: str) -> List[Tuple[str, datetime]]:
        """Extract only future dates."""
        all_dates = self.extract_dates(text)
        now = datetime.now()
        future_dates = [(d_str, dt) for d_str, dt in all_dates if dt > now]
        return future_dates
    
    def get_latest_future_date(self, text: str) -> Optional[datetime]:
        """Get the latest future date from text."""
        future_dates = self.extract_future_dates(text)
        if future_dates:
            # Sort by date and return the latest
            future_dates.sort(key=lambda x: x[1])
            return future_dates[-1][1]
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object."""
        date_str = date_str.strip()
        
        # Try different formats
        formats = [
            '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%m-%d-%Y',
            '%d/%m/%y', '%d-%m-%y', '%m/%d/%y', '%m-%d-%y',
            '%d %b %Y', '%d %B %Y', '%b %d %Y', '%B %d %Y',
            '%Y/%m/%d', '%Y-%m-%d',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None

# Singleton
date_extractor = DateExtractor()
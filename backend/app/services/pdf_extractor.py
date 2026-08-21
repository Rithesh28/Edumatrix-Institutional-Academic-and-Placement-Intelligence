import pdfplumber
import re
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime

class PDFExtractor:
    """Extract text and structured data from PDF files"""
    
    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """Extract raw text from PDF file path"""
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return ""
        return text.strip()
    
    @staticmethod
    def extract_text_from_upload(file) -> str:
        """Extract text from uploaded file object"""
        text = ""
        try:
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return ""
        return text.strip()
    
    @staticmethod
    def extract_dates_from_text(text: str) -> List[datetime]:
        """Extract dates from text using regex patterns (fallback)"""
        dates = []
        
        # Pattern 1: 2026-05-15 (ISO format)
        pattern1 = r'\d{4}-\d{2}-\d{2}'
        for match in re.findall(pattern1, text):
            try:
                dates.append(datetime.strptime(match, '%Y-%m-%d'))
            except:
                pass
        
        # Pattern 2: 15/05/2026 or 05/15/2026
        pattern2 = r'\d{1,2}/\d{1,2}/\d{4}'
        for match in re.findall(pattern2, text):
            try:
                if int(match.split('/')[0]) > 12:
                    dates.append(datetime.strptime(match, '%d/%m/%Y'))
                else:
                    dates.append(datetime.strptime(match, '%m/%d/%Y'))
            except:
                pass
        
        # Pattern 3: 03 May 2026, 20 May 2026
        pattern3 = r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})\b'
        for match in re.findall(pattern3, text, re.IGNORECASE):
            try:
                day, month, year = match
                month_num = {
                    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                }.get(month.capitalize()[:3], 1)
                dates.append(datetime(int(year), month_num, int(day)))
            except:
                pass
        
        # Pattern 4: May 15, 2026, May 15 2026
        pattern4 = r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b'
        for match in re.findall(pattern4, text, re.IGNORECASE):
            try:
                month, day, year = match
                month_num = {
                    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                }.get(month.capitalize()[:3], 1)
                dates.append(datetime(int(year), month_num, int(day)))
            except:
                pass
        
        # Remove duplicates and return
        unique_dates = list(set(dates))
        return unique_dates
    
    @staticmethod
    def extract_entities_from_text(text: str) -> Dict:
        """Extract basic entities using regex (fallback)"""
        entities = {
            "dates": [],
            "numbers": [],
            "emails": [],
            "urls": []
        }
        
        # Extract numbers
        numbers = re.findall(r'\b\d+\b', text)
        entities["numbers"] = list(set(numbers))[:10]
        
        # Extract emails
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        entities["emails"] = emails
        
        # Extract URLs
        urls = re.findall(r'https?://[^\s]+', text)
        entities["urls"] = urls
        
        # Extract dates using regex
        date_objects = PDFExtractor.extract_dates_from_text(text)
        entities["dates"] = [d.isoformat() for d in date_objects]
        
        return entities
    
    @staticmethod
    def extract_structured_data(text: str, data_type: str = "circular") -> dict:
        """Extract structured data based on document type using GLiNER"""
        
        # Try to use GLiNER
        try:
            from .ner_extractor import ner_extractor
            
            if ner_extractor.is_loaded:
                print("✅ Using GLiNER for extraction")
                if data_type == "circular":
                    result = ner_extractor.extract_exam_circular_info(text)
                    return result
                elif data_type == "assignment":
                    return ner_extractor.extract_assignment_info(text)
                elif data_type == "exam_duty":
                    return ner_extractor.extract_exam_duty_info(text)
                else:
                    return {"dates": ner_extractor.extract_dates(text)}
            else:
                print("⚠️ GLiNER not loaded, using regex fallback")
        except Exception as e:
            print(f"❌ GLiNER error: {e}")
        
        # Fallback to regex
        return {
            "dates": [d.isoformat() for d in PDFExtractor.extract_dates_from_text(text)],
            "exam_name": None,
            "subject": None,
            "venue": None,
            "deadline": None,
            "entities": PDFExtractor.extract_entities_from_text(text)
        }
    
    @staticmethod
    def extract_exam_name(text: str) -> Optional[str]:
        """Extract exam/semester name using regex"""
        patterns = [
            r'(Semester|Final|Mid-term|Annual|End-of-year)\s+(Examination|Exam)s?\s+(\w+(?:\s+\w+)*)',
            r'Subject:\s*(.+?)(?:\n|$)',
            r'Examination\s+for\s+(.+?)(?:\n|$)'
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip() if match.lastindex >= 1 else match.group(0).strip()
        return None


# Singleton instance
pdf_extractor = PDFExtractor()
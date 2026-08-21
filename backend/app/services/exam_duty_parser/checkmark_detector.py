"""
Checkmark Detector for Exam Duty Extraction

This module detects visual checkmarks (✓ ✔ ✅) in text or images.
It supports:
- Text-based detection (searching for unicode characters)
- Image-based detection using template matching
- Position mapping to table cells
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Union, Tuple
try:
    from PIL import Image
except ImportError:
    Image = None


class CheckmarkDetector:
    """
    Detects checkmarks in text and images.
    
    Checkmark patterns:
    - ✓ (U+2713)
    - ✔ (U+2714)
    - ✅ (U+2705)
    - ☑ (U+2611)
    - [x] or [X] (markdown style)
    - (x) or (X) (text style)
    """
    
    # Unicode checkmark patterns
    CHECKMARK_PATTERNS = [
        '✓',   # U+2713
        '✔',   # U+2714
        '✅',   # U+2705
        '☑',   # U+2611
        '🗸',   # U+1F5F8
        '✅',   # U+2705
    ]
    
    # Regex patterns for checkmarks
    PATTERN = re.compile(
        r'[✓✔✅☑🗸]|\[[xX]\]|\([xX]\)',
        re.UNICODE
    )
    
    def __init__(self):
        """Initialize checkmark detector."""
        self._checkmarks = []
    
    def detect(self, text: str) -> bool:
        """
        Detect if text contains a checkmark.
        
        Args:
            text: Text to check
            
        Returns:
            True if checkmark found, False otherwise
        """
        if not text:
            return False
        
        # Check for unicode checkmarks
        for char in self.CHECKMARK_PATTERNS:
            if char in text:
                return True
        
        # Check for regex patterns
        return bool(self.PATTERN.search(text))
    
    def detect_all(self, text: str) -> List[Dict[str, Union[str, int]]]:
        """
        Find all checkmarks in text with their positions.
        
        Args:
            text: Text to search
            
        Returns:
            List of dicts with checkmark info:
            {
                'character': str,
                'position': int,
                'context': str
            }
        """
        results = []
        
        # Check for unicode checkmarks
        for i, char in enumerate(text):
            if char in self.CHECKMARK_PATTERNS:
                results.append({
                    'character': char,
                    'position': i,
                    'context': text[max(0, i-10):i+10]
                })
        
        # Check for regex patterns
        for match in self.PATTERN.finditer(text):
            results.append({
                'character': match.group(),
                'position': match.start(),
                'context': text[max(0, match.start()-10):match.end()+10]
            })
        
        return results
    
    def detect_in_table_cell(self, cell_content: str) -> bool:
        """
        Detect if a table cell contains a checkmark.
        
        Args:
            cell_content: Content of the table cell
            
        Returns:
            True if checkmark found, False otherwise
        """
        return self.detect(cell_content)
    
    def detect_in_image(self, image: Image.Image) -> List[Dict]:
        """
        Detect checkmarks in an image.
        
        This is a basic implementation. For production use,
        consider using computer vision techniques.
        
        Args:
            image: PIL Image object
            
        Returns:
            List of checkmark positions
        """
        # Basic approach: OCR the image and check text
        try:
            import pytesseract
            text = pytesseract.image_to_string(image)
            if self.detect(text):
                return [{'method': 'ocr', 'text': text}]
        except Exception:
            pass
        
        return []
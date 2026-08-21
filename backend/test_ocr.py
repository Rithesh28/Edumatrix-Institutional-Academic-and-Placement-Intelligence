"""
Test OCR extraction from exam duty image
"""

import os
import sys
from app.services.file_storage.text_extractor import text_extractor

image_path = '/app/uploads/exam_duties/exam_duty_5_0047f020-00aa-49b9-b799-1cec560afd55.png'

print('=' * 60)
print('OCR Test')
print('=' * 60)

if not os.path.exists(image_path):
    print(f'❌ Image not found: {image_path}')
    sys.exit(1)

print(f'📄 Testing OCR on: {os.path.basename(image_path)}')

result = text_extractor.extract_text(image_path)

print('\n📊 Results:')
print('=' * 60)
print(f'Success: {result["success"]}')
print(f'Text length: {len(result.get("text", ""))} characters')
print(f'Extractor used: {result.get("extractor_used")}')
print(f'Error: {result.get("error")}')
print('=' * 60)

if result['text']:
    print('\n📝 Extracted text (first 500 characters):')
    print('-' * 60)
    print(result['text'][:500])
    print('-' * 60)
else:
    print('\n⚠️ No text extracted from image')
    print('This is expected if the image is a complex table without clear text.')
"""
Test script to verify text extractor
"""

import os
import logging
from app.services.file_storage.text_extractor import text_extractor

logging.basicConfig(level=logging.INFO)

def test_text_extractor():
    """Test text extractor with various file types."""
    
    print("=" * 50)
    print("Testing Text Extractor")
    print("=" * 50)
    
    # Test with a sample text
    test_dir = "/app/uploads/exam_duties"
    
    # Check if there are any files to test
    if os.path.exists(test_dir):
        files = os.listdir(test_dir)
        if files:
            test_file = os.path.join(test_dir, files[0])
            print(f"\n📄 Testing with: {test_file}")
            
            result = text_extractor.extract_text(test_file)
            
            print(f"\n📊 Result:")
            print(f"   Success: {result['success']}")
            print(f"   Extractor: {result.get('extractor_used')}")
            print(f"   Text length: {len(result.get('text', ''))}")
            print(f"   Error: {result.get('error')}")
            
            if result['success'] and result['text']:
                print(f"\n📝 First 200 chars:")
                print("-" * 40)
                print(result['text'][:200] + "...")
                print("-" * 40)
            
            # Test embedding extraction
            print("\n🔍 Testing embedding extraction:")
            embedding_text = text_extractor.extract_text_for_embedding(test_file)
            if embedding_text:
                print(f"   Clean text length: {len(embedding_text)}")
                print(f"   First 100 chars: {embedding_text[:100]}...")
            else:
                print("   ❌ No text extracted for embedding")
        else:
            print("\n⚠️ No files found in test directory")
    else:
        print(f"\n⚠️ Test directory not found: {test_dir}")
    
    # Test with different file types if available
    print("\n" + "=" * 50)
    print("Test complete!")
    print("=" * 50)


if __name__ == "__main__":
    test_text_extractor()
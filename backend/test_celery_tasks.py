"""
Test script to verify Celery tasks
"""

import logging
from app.tasks.file_tasks import generate_embedding, cleanup_temporary_files

logging.basicConfig(level=logging.INFO)

def test_tasks():
    """Test Celery tasks."""
    
    print("=" * 50)
    print("Testing Celery Tasks")
    print("=" * 50)
    
    # Test cleanup task
    print("\n🔄 Testing cleanup task...")
    result = cleanup_temporary_files.delay()
    print(f"   Task ID: {result.id}")
    print(f"   Status: {'✅ Task queued' if result.id else '❌ Failed'}")
    
    print("\n" + "=" * 50)
    print("Test complete!")
    print("=" * 50)


if __name__ == "__main__":
    test_tasks()
    
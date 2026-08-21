"""
Debug Celery Task Execution
"""

from app.tasks.file_tasks import generate_embedding
from app.services.file_storage.qdrant_client import qdrant_client
import time
import sys

file_id = '76545034-74f1-4991-bbb2-efcfe0ed0cd6'

print('=' * 60)
print('Debug Celery Task')
print('=' * 60)

print(f'File ID: {file_id}')

# Check if vector exists before
print('\n📊 Before task execution:')
vector_before = qdrant_client.get_vector(file_id)
print(f'   Vector exists: {vector_before is not None}')

# Trigger task
print('\n📤 Triggering task...')
result = generate_embedding.delay(file_id)
print(f'   Task ID: {result.id}')

# Wait for processing
print('\n⏳ Waiting for task to complete...')
time.sleep(15)

# Check if vector was created
print('\n📊 After task execution:')
vector = qdrant_client.get_vector(file_id)
if vector:
    print(f'✅ Vector found! Length: {len(vector)}')
else:
    print('❌ No vector found')

# Check Celery logs for errors
print('\n🔍 Check Celery worker logs for errors:')
print('   Run: docker-compose logs celery-worker --tail 30')
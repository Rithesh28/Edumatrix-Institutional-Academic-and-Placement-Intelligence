"""
Manually generate embedding for a file
"""

from app.tasks.file_tasks import generate_embedding
from app.services.file_storage.qdrant_client import qdrant_client
from app.services.embedding_service import embedding_service
from app.core.database import SessionLocal
from app.models.file import File
import uuid

file_id = '66d8363b-9128-46e9-9c04-5457ca27e2db'

print('=' * 60)
print(f'Manually generating embedding for: {file_id}')
print('=' * 60)

# Check if file exists
db = SessionLocal()
file = db.query(File).filter(File.id == uuid.UUID(file_id)).first()
if file:
    print(f'✅ File found: {file.filename}')
    print(f'   Bucket: {file.bucket}')
    print(f'   Object Key: {file.object_key}')
else:
    print('❌ File not found in database')
    db.close()
    exit()

db.close()

# Generate embedding
print('\n🔄 Generating embedding...')
generate_embedding(file_id)

# Check if vector was created
print('\n📊 Checking Qdrant...')
vector = qdrant_client.get_vector(file_id)
if vector:
    print(f'✅ Vector found! Length: {len(vector)}')
else:
    print('❌ No vector found')
    exit()

# Test search
print('\n🔍 Testing search...')
query = 'test document'
query_vector = embedding_service.embed_text(query)
if query_vector:
    results = qdrant_client.search(query_vector, limit=5)
    print(f'Found {len(results)} results:')
    for r in results:
        payload = r.get('payload', {})
        title = payload.get('title', 'Unknown')
        score = r.get('score', 0)
        print(f'   - {title} (Score: {score:.4f})')
else:
    print('❌ Failed to generate query embedding')

print('\n' + '=' * 60)
print('Done!')
print('=' * 60)
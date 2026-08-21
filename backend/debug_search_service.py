"""
Debug search service
"""

from app.services.file_storage.search_service import search_service
from app.schemas.file import FileSearchQuery
from app.core.database import SessionLocal
from app.services.embedding_service import embedding_service
from app.services.file_storage.qdrant_client import qdrant_client

print('=' * 60)
print('Debug Search Service')
print('=' * 60)

# 1. Check if there are any vectors in Qdrant
print('\n📊 Checking Qdrant...')
result = qdrant_client.search([0.0] * 384, limit=10)
print(f'Found {len(result)} points in Qdrant')
for r in result:
    payload = r.get('payload', {})
    print(f'   - {payload.get("title")} (Score: {r.get("score", 0):.4f})')

# 2. Test embedding generation
print('\n🔢 Testing embedding...')
test_text = 'test document'
embedding = embedding_service.embed_text(test_text)
if embedding:
    print(f'   ✅ Embedding generated: {len(embedding)} dimensions')
else:
    print('   ❌ Failed to generate embedding')

# 3. Test search service
print('\n🔍 Testing search service...')
db = SessionLocal()
try:
    query = FileSearchQuery(query='test', limit=10)
    result = search_service.search(db, query, None)
    print(f'   Found {result.total} results')
    for r in result.results:
        print(f'      - {r.title} (Score: {r.score:.4f})')
finally:
    db.close()
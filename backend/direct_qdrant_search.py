"""
Direct Qdrant Search Test
"""

from app.services.embedding_service import embedding_service
from app.services.file_storage.qdrant_client import qdrant_client

print('=' * 60)
print('Direct Qdrant Search Test')
print('=' * 60)

# Generate query embedding
query = 'artificial intelligence machine learning'
print(f'\n🔍 Query: {query}')

query_vector = embedding_service.embed_text(query)
if not query_vector:
    print('❌ Failed to generate query embedding')
    exit()

print(f'✅ Query embedding generated, length: {len(query_vector)}')

# Search directly in Qdrant
results = qdrant_client.search(
    query_vector=query_vector,
    limit=10,
    score_threshold=0.1
)

print(f'\n📊 Found {len(results)} results:')
for r in results:
    payload = r.get('payload', {})
    print(f'   - Score: {r.get("score", 0):.4f}')
    print(f'     File ID: {payload.get("file_id")}')
    print(f'     Title: {payload.get("title")}')
    print(f'     Department: {payload.get("department")}')
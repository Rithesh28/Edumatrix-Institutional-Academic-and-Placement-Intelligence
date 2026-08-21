"""
Test Qdrant directly
"""

from app.services.file_storage.qdrant_client import qdrant_client
from app.services.embedding_service import embedding_service

print('=' * 60)
print('Testing Qdrant Directly')
print('=' * 60)

# Test search directly
query = 'test document'
print(f'\n🔍 Query: {query}')
query_vector = embedding_service.embed_text(query)

if query_vector:
    results = qdrant_client.search(query_vector, limit=10)
    
    print(f'Direct Qdrant search found {len(results)} results:')
    for r in results:
        payload = r.get('payload', {})
        title = payload.get('title', 'Unknown')
        score = r.get('score', 0)
        department = payload.get('department', 'Unknown')
        file_id = payload.get('file_id', 'Unknown')
        print(f'   - {title} (Score: {score:.4f})')
        print(f'     Department: {department}')
        print(f'     File ID: {file_id}')
else:
    print('❌ Failed to generate query embedding')

print('\n' + '=' * 60)
print('Done!')
print('=' * 60)
"""
Test different search queries directly with Qdrant
"""

from app.services.embedding_service import embedding_service
from app.services.file_storage.qdrant_client import qdrant_client

print('=' * 60)
print('Testing Search Queries')
print('=' * 60)

queries = ['direct', 'test', 'embedding', 'document', 'AI', 'machine learning']

for q in queries:
    print(f'\n🔍 Query: "{q}"')
    query_vector = embedding_service.embed_text(q)
    if query_vector:
        results = qdrant_client.search(query_vector, limit=5, score_threshold=0.1)
        print(f'   Found {len(results)} results')
        for r in results:
            payload = r.get('payload', {})
            title = payload.get('title', 'Unknown')
            score = r.get('score', 0)
            print(f'      - {title} (Score: {score:.4f})')
    else:
        print('   ❌ Failed to generate embedding')
"""
Check all points in Qdrant
"""

from app.services.file_storage.qdrant_client import qdrant_client

print('=' * 60)
print('All Points in Qdrant')
print('=' * 60)

result = qdrant_client.search(
    query_vector=[0.0] * 384,
    limit=20
)

print(f'\nFound {len(result)} points:')
for r in result:
    payload = r.get('payload', {})
    title = payload.get('title', 'Unknown')
    department = payload.get('department', 'Unknown')
    file_id = payload.get('file_id', 'Unknown')
    score = r.get('score', 0)
    print(f'   - {title}')
    print(f'     Department: {department}')
    print(f'     File ID: {file_id}')
    print(f'     Score: {score:.4f}')
    print()
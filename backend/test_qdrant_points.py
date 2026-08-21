"""
Get all points from Qdrant
"""

from app.services.file_storage.qdrant_client import qdrant_client

print('=' * 60)
print('Getting All Points from Qdrant')
print('=' * 60)

# Get collection info
info = qdrant_client.get_collection_info()
print(f'\n📊 Collection: {info.get("name")}')
print(f'   Points: {info.get("points_count")}')
print(f'   Vector Size: {info.get("vector_size")}')

# Get all points
print('\n📋 All points:')
result = qdrant_client.search(
    query_vector=[0.0] * 384,
    limit=50
)

if result:
    for r in result:
        payload = r.get('payload', {})
        file_id = payload.get('file_id', 'Unknown')
        title = payload.get('title', 'Unknown')
        department = payload.get('department', 'Unknown')
        file_type = payload.get('file_type', 'Unknown')
        print(f'   - {title}')
        print(f'     File ID: {file_id}')
        print(f'     Department: {department}')
        print(f'     Type: {file_type}')
        print(f'     Score: {r.get("score", 0):.4f}')
else:
    print('   No points found')

print('\n' + '=' * 60)
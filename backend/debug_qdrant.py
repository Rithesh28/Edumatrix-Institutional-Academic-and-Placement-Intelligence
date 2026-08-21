"""
Debug Qdrant Storage
"""

from app.services.file_storage.qdrant_client import qdrant_client

print('=' * 60)
print('Check Qdrant Storage')
print('=' * 60)

# Get all points in the collection
info = qdrant_client.get_collection_info()
print(f'Points in collection: {info.get("points_count")}')

# Try to get the vector for our file
file_id = '9dcb74f1-d80a-48cc-90f7-f7ef429299f9'
vector = qdrant_client.get_vector(file_id)
if vector:
    print(f'✅ Vector found! Length: {len(vector)}')
else:
    print(f'❌ No vector found for file: {file_id}')

# Get payload
payload = qdrant_client.get_payload(file_id)
if payload:
    print('✅ Payload found:')
    for key, value in payload.items():
        print(f'   {key}: {value}')
else:
    print('❌ No payload found')
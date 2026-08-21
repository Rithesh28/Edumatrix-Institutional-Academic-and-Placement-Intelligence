"""
Simple embedding test - bypass Celery
"""

from app.services.file_storage.text_extractor import text_extractor
from app.services.embedding_service import embedding_service
from app.services.file_storage.minio_client import minio_client
from app.services.file_storage.qdrant_client import qdrant_client
from app.core.database import SessionLocal
from app.models.file import File
import uuid

file_id = '76545034-74f1-4991-bbb2-efcfe0ed0cd6'

print('=' * 60)
print('Simple Embedding Test (Bypass Celery)')
print('=' * 60)

db = SessionLocal()

try:
    # Get file from database
    file = db.query(File).filter(File.id == uuid.UUID(file_id)).first()
    if not file:
        print(f'❌ File not found: {file_id}')
        exit()

    print(f'📄 File: {file.filename}')
    print(f'   Bucket: {file.bucket}')
    print(f'   Object Key: {file.object_key}')

    # Download from MinIO
    print('\n📥 Downloading from MinIO...')
    content = minio_client.download_file(file.bucket, file.object_key)
    print(f'   Downloaded {len(content)} bytes')

    # Extract text
    print('\n📝 Extracting text...')
    extracted_text = text_extractor.extract_text_for_embedding(
        file_path=file.filename,
        content=content
    )
    if extracted_text:
        print(f'   Extracted {len(extracted_text)} characters')
        print(f'   Preview: {extracted_text[:100]}...')
    else:
        print('   ❌ No text extracted')
        exit()

    # Generate embedding
    print('\n🔢 Generating embedding...')
    vector = embedding_service.embed_text(extracted_text)
    if vector:
        print(f'   ✅ Embedding generated! Length: {len(vector)}')
    else:
        print('   ❌ Failed to generate embedding')
        exit()

    # Store in Qdrant
    print('\n💾 Storing in Qdrant...')
    payload = {
        'file_id': str(file.id),
        'file_type': file.file_type,
        'department': file.department,
        'uploaded_by': str(file.uploaded_by) if file.uploaded_by else None,
        'title': file.title,
        'created_at': file.created_at.isoformat() if file.created_at else None
    }
    qdrant_client.upsert_vector(str(file.id), vector, payload)
    print('   ✅ Stored in Qdrant')

    # Verify
    print('\n✅ Verifying...')
    stored_vector = qdrant_client.get_vector(str(file.id))
    if stored_vector:
        print(f'   ✅ Vector found! Length: {len(stored_vector)}')
    else:
        print('   ❌ Vector not found after storage')

finally:
    db.close()
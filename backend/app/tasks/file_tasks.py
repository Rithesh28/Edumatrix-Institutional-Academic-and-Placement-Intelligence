"""
Celery Tasks for File Processing
"""

import logging
import uuid
from typing import Optional, Dict, Any
from celery import shared_task
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..models.file import File, FileStatus
from ..models.user import User
from ..services.file_storage.minio_client import minio_client
from ..services.file_storage.text_extractor import text_extractor
from ..services.embedding_service import embedding_service
from ..services.file_storage.qdrant_client import qdrant_client

logger = logging.getLogger(__name__)


@shared_task(name="file_tasks.generate_embedding", bind=True, max_retries=3)
def generate_embedding(self, file_id: str):
    """
    Generate embedding for a file and store in Qdrant.
    """
    logger.info(f"🔄 Generating embedding for file: {file_id}")
    
    db = SessionLocal()
    try:
        # Get file from database
        file = db.query(File).filter(
            File.id == uuid.UUID(file_id) if isinstance(file_id, str) else file_id,
            File.status != FileStatus.DELETED
        ).first()
        
        if not file:
            logger.warning(f"⚠️ File not found: {file_id}")
            return None
        
        logger.info(f"📄 File found: {file.filename}")
        
        # Check if embedding already exists in Qdrant
        existing_vector = qdrant_client.get_vector(str(file_id))
        if existing_vector:
            logger.info(f"ℹ️ Embedding already exists for file: {file_id}")
            return {"file_id": str(file_id), "status": "already_exists"}
        
        # Download file content from MinIO
        try:
            content = minio_client.download_file(file.bucket, file.object_key)
            logger.info(f"📥 Downloaded {len(content)} bytes from MinIO")
        except Exception as e:
            logger.error(f"❌ Failed to download file from MinIO: {str(e)}")
            self.retry(countdown=60, exc=e)
            return None
        
        # Extract text from file
        extracted_text = text_extractor.extract_text_for_embedding(
            file_path=file.filename,
            content=content
        )
        
        if not extracted_text:
            logger.warning(f"⚠️ No text extracted from file: {file_id}")
            return None
        
        logger.info(f"📝 Extracted {len(extracted_text)} characters")
        
        # Generate vector embedding
        vector = embedding_service.embed_text(extracted_text)
        if not vector:
            logger.error(f"❌ Failed to generate embedding for file: {file_id}")
            return None
        
        logger.info(f"✅ Embedding generated! Length: {len(vector)}")
        
        # Store in Qdrant
        payload = {
            "file_id": str(file.id),
            "file_type": file.file_type,
            "department": file.department,
            "uploaded_by": str(file.uploaded_by) if file.uploaded_by else None,
            "title": file.title,
            "filename": file.filename,
            "created_at": file.created_at.isoformat() if file.created_at else None,
            "version": file.version
        }
        
        result = qdrant_client.upsert_vector(
            file_id=str(file_id),
            vector=vector,
            payload=payload
        )
        
        if result:
            logger.info(f"✅ Embedding stored in Qdrant for file: {file_id}")
            
            # Update file record with embedding status
            file.extra_data = file.extra_data or {}
            file.extra_data["embedding_generated"] = True
            db.commit()
            logger.info("✅ Database updated with embedding status")
            return {"file_id": str(file_id), "status": "success"}
        else:
            logger.error(f"❌ Failed to store embedding in Qdrant for file: {file_id}")
            return None
        
    except Exception as e:
        logger.error(f"❌ Embedding generation failed for {file_id}: {str(e)}", exc_info=True)
        db.rollback()
        self.retry(countdown=60, exc=e)
    finally:
        db.close()


@shared_task(name="file_tasks.process_upload", bind=True, max_retries=3)
def process_upload(self, file_id: str, user_id: int):
    """Process uploaded file asynchronously."""
    logger.info(f"🔄 Processing upload for file: {file_id} by user {user_id}")
    try:
        generate_embedding.delay(str(file_id))
        logger.info(f"✅ Upload processing complete for file: {file_id}")
        return {"file_id": str(file_id), "status": "enqueued"}
    except Exception as e:
        logger.error(f"❌ Upload processing failed for {file_id}: {str(e)}")
        self.retry(countdown=60, exc=e)


@shared_task(name="file_tasks.delete_file_vectors", bind=True, max_retries=3)
def delete_file_vectors(self, file_id: str):
    """Delete vector points from Qdrant for a file."""
    logger.info(f"🗑️ Deleting vectors for file: {file_id}")
    try:
        qdrant_client.delete_vector(str(file_id))
        logger.info(f"✅ Vectors deleted for file: {file_id}")
        return {"file_id": str(file_id), "status": "deleted"}
    except Exception as e:
        logger.error(f"❌ Vector deletion failed for {file_id}: {str(e)}")
        self.retry(countdown=60, exc=e)


@shared_task(name="file_tasks.cleanup_temporary_files", max_retries=2)
def cleanup_temporary_files():
    """Clean up vectors for soft-deleted files."""
    logger.info("🔄 Running cleanup task for deleted files...")
    db = SessionLocal()
    try:
        deleted_files = db.query(File).filter(File.status == FileStatus.DELETED).all()
        count = 0
        for file in deleted_files:
            try:
                qdrant_client.delete_vector(str(file.id))
                count += 1
            except Exception as e:
                logger.error(f"❌ Failed to clean up vector for {file.id}: {str(e)}")
        logger.info(f"✅ Cleanup complete. Processed {count} deleted files.")
        return {"cleaned_count": count}
    except Exception as e:
        logger.error(f"❌ Cleanup task failed: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()


@shared_task(name="file_tasks.sync_embedding_batch", max_retries=2)
def sync_embedding_batch(limit: int = 100):
    """Generate embeddings for active files that don't have them yet."""
    logger.info(f"🔄 Syncing embeddings for up to {limit} files...")
    db = SessionLocal()
    try:
        files = db.query(File).filter(File.status == FileStatus.ACTIVE).limit(limit).all()
        
        files_to_process = []
        for file in files:
            extra_data = file.extra_data or {}
            if not extra_data.get("embedding_generated", False):
                files_to_process.append(file)
        
        if not files_to_process:
            logger.info("ℹ️ No files need embedding sync")
            return {"synced_count": 0}
        
        logger.info(f"📤 Syncing embeddings for {len(files_to_process)} files...")
        
        for file in files_to_process:
            generate_embedding.delay(str(file.id))
        
        logger.info(f"✅ Initiated embedding sync for {len(files_to_process)} files")
        return {"synced_count": len(files_to_process)}
    except Exception as e:
        logger.error(f"❌ Embedding sync failed: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()


@shared_task(name="file_tasks.update_search_index", bind=True, max_retries=3)
def update_search_index(self, file_id: str, update_payload: Dict[str, Any]):
    """Update search index when file metadata changes."""
    logger.info(f"🔄 Updating search index for file: {file_id}")
    try:
        existing_vector = qdrant_client.get_vector(str(file_id))
        if not existing_vector:
            logger.warning(f"⚠️ No vector found for file: {file_id}")
            return {"file_id": str(file_id), "status": "vector_not_found"}
        
        existing_payload = qdrant_client.get_payload(str(file_id)) or {}
        existing_payload.update(update_payload)
        qdrant_client.upsert_vector(str(file_id), existing_vector, existing_payload)
        logger.info(f"✅ Search index updated for file: {file_id}")
        return {"file_id": str(file_id), "status": "updated"}
    except Exception as e:
        logger.error(f"❌ Search index update failed for {file_id}: {str(e)}")
        self.retry(countdown=60, exc=e)


@shared_task(name="file_tasks.check_file_integrity", max_retries=2)
def check_file_integrity(file_id: str):
    """Check file integrity between MinIO, Database, and Qdrant."""
    logger.info(f"🔍 Checking integrity for file: {file_id}")
    db = SessionLocal()
    try:
        file = db.query(File).filter(
            File.id == uuid.UUID(file_id) if isinstance(file_id, str) else file_id
        ).first()
        if not file:
            logger.warning(f"⚠️ File not found in database: {file_id}")
            return {"file_id": str(file_id), "status": "not_in_db"}
        
        try:
            minio_client.get_object_info(file.bucket, file.object_key)
            minio_exists = True
        except Exception:
            minio_exists = False
        
        vector_exists = qdrant_client.get_vector(str(file_id)) is not None
        
        issues = []
        if not minio_exists and file.status != FileStatus.DELETED:
            issues.append("Missing in MinIO")
            logger.warning(f"⚠️ File missing in MinIO: {file_id}")
        
        if not vector_exists and file.status == FileStatus.ACTIVE:
            issues.append("Missing vector in Qdrant")
            logger.warning(f"⚠️ Vector missing in Qdrant: {file_id}")
        
        return {
            "file_id": str(file_id),
            "minio_exists": minio_exists,
            "vector_exists": vector_exists,
            "issues": issues,
            "status": "healthy" if not issues else "unhealthy"
        }
    except Exception as e:
        logger.error(f"❌ Integrity check failed for {file_id}: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()


@shared_task(name="file_tasks.regenerate_embeddings_for_department", max_retries=2)
def regenerate_embeddings_for_department(department: str, limit: int = 500):
    """Regenerate embeddings for all files in a department."""
    logger.info(f"🔄 Regenerating embeddings for department: {department}")
    db = SessionLocal()
    try:
        files = db.query(File).filter(
            File.department == department,
            File.status == FileStatus.ACTIVE
        ).limit(limit).all()
        
        if not files:
            logger.info(f"ℹ️ No files found for department: {department}")
            return {"count": 0}
        
        logger.info(f"📤 Regenerating embeddings for {len(files)} files in {department}...")
        
        for file in files:
            qdrant_client.delete_vector(str(file.id))
            generate_embedding.delay(str(file.id))
        
        logger.info(f"✅ Embedding regeneration initiated for {len(files)} files")
        return {"department": department, "count": len(files)}
    except Exception as e:
        logger.error(f"❌ Embedding regeneration failed: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()


@shared_task(name="file_tasks.process_file_version", bind=True, max_retries=3)
def process_file_version(self, file_id: str, version_number: int):
    """Process a new file version."""
    logger.info(f"🔄 Processing version {version_number} for file: {file_id}")
    try:
        generate_embedding.delay(str(file_id))
        update_search_index.delay(str(file_id), {"version": version_number})
        logger.info(f"✅ Version {version_number} processed for file: {file_id}")
        return {"file_id": str(file_id), "version": version_number}
    except Exception as e:
        logger.error(f"❌ Version processing failed for {file_id}: {str(e)}")
        self.retry(countdown=60, exc=e)

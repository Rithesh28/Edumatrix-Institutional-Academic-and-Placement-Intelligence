"""
File Service - Core Business Logic
"""

import os
import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import UploadFile

from ...models.file import File, FileStatus
from ...models.file_version import FileVersion
from ...models.user import User
from ...schemas.file import FileUpdate
from ...core.config import settings
from .minio_client import minio_client
from .text_extractor import text_extractor
from ..embedding_service import embedding_service
from .qdrant_client import qdrant_client

logger = logging.getLogger(__name__)


class FileService:
    """
    Core file service for all file operations.
    """
    
    def __init__(self):
        self.buckets = {
            'exam_duty': 'exam-duties',
            'assignment': 'assignments',
            'circular': 'circulars',
            'resume': 'resumes',
            'timetable': 'timetables',
            'certificate': 'certificates',
            'placement_doc': 'placement-docs',
            'other': 'other'
        }
    
    def _get_bucket(self, file_type: str) -> str:
        """Get bucket name for file type."""
        return self.buckets.get(file_type, 'other')
    
    def _generate_object_key(self, file_id: uuid.UUID, filename: str) -> str:
        """Generate object key for MinIO."""
        safe_filename = filename.replace(' ', '_')
        return f"{file_id}/{safe_filename}"
    
    async def upload_file(
        self,
        db: Session,
        file: UploadFile,
        uploaded_by: User,  # User object, not just ID
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        department: Optional[str] = None,
        file_type: str = 'other',
        hod_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to the system.
        """
        try:
            # Read file content
            content = await file.read()
            file_size = len(content)
            
            # Generate file ID
            file_id = uuid.uuid4()
            
            # Determine bucket
            bucket = self._get_bucket(file_type)
            
            # Generate object key
            object_key = self._generate_object_key(file_id, file.filename)
            
            # Upload to MinIO
            minio_client.upload_file(
                bucket=bucket,
                object_key=object_key,
                file_data=content,
                content_type=file.content_type or "application/octet-stream"
            )
            
            # Extract text for embedding
            extracted_text = text_extractor.extract_text_for_embedding(
                file_path=file.filename,
                content=content
            )
            
            # Generate embedding if text available
            vector = None
            if extracted_text:
                vector = embedding_service.embed_text(extracted_text)
            
            # Create file record in database
            db_file = File(
                id=file_id,
                filename=file.filename,
                file_size=file_size,
                mime_type=file.content_type or "application/octet-stream",
                bucket=bucket,
                object_key=object_key,
                title=title or file.filename,
                description=description,
                tags=tags or [],
                department=department or uploaded_by.department,
                file_type=file_type,
                uploaded_by=uploaded_by.id,  # User.id is Integer
                hod_id=hod_id,
                version=1,
                is_latest=True,
                status=FileStatus.ACTIVE,
                extra_data=extra_data or {}
            )
            db.add(db_file)
            db.commit()
            db.refresh(db_file)
            
            # Store vector in Qdrant if available
            if vector:
                qdrant_payload = {
                    "file_id": str(file_id),
                    "file_type": file_type,
                    "department": department or uploaded_by.department,
                    "uploaded_by": str(uploaded_by.id),
                    "title": title or file.filename,
                    "created_at": db_file.created_at.isoformat() if db_file.created_at else None
                }
                qdrant_client.upsert_vector(
                    file_id=str(file_id),
                    vector=vector,
                    payload=qdrant_payload
                )
            
            logger.info(f"✅ File uploaded: {file.filename} (ID: {file_id})")
            
            return {
                'success': True,
                'file_id': file_id,
                'file': db_file,
                'message': 'File uploaded successfully'
            }
            
        except Exception as e:
            logger.error(f"❌ File upload failed: {str(e)}")
            db.rollback()
            raise
    
    def get_file(self, db: Session, file_id: uuid.UUID) -> Optional[File]:
        """Get file by ID."""
        return db.query(File).filter(
            File.id == file_id,
            File.status != FileStatus.DELETED
        ).first()
    
    def get_file_with_versions(self, db: Session, file_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get file with all versions."""
        file = self.get_file(db, file_id)
        if not file:
            return None
        
        versions = db.query(FileVersion).filter(
            FileVersion.file_id == file_id
        ).order_by(FileVersion.version_number.desc()).all()
        
        return {
            'file': file,
            'versions': versions
        }
    
    def update_file_metadata(
        self,
        db: Session,
        file_id: uuid.UUID,
        update_data: FileUpdate
    ) -> Optional[File]:
        """Update file metadata."""
        file = self.get_file(db, file_id)
        if not file:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if hasattr(file, key):
                setattr(file, key, value)
        
        file.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(file)
        
        # Update Qdrant payload if needed
        if any(key in update_dict for key in ['title', 'department', 'file_type']):
            payload = {
                "file_id": str(file.id),
                "file_type": file.file_type,
                "department": file.department,
                "uploaded_by": str(file.uploaded_by) if file.uploaded_by else None,
                "title": file.title,
                "created_at": file.created_at.isoformat() if file.created_at else None
            }
            qdrant_client.update_payload(str(file_id), payload)
        
        logger.info(f"✅ File metadata updated: {file_id}")
        return file
    
    def delete_file(self, db: Session, file_id: uuid.UUID, permanent: bool = False) -> bool:
        """Delete a file."""
        file = self.get_file(db, file_id)
        if not file:
            return False
        
        if permanent:
            minio_client.delete_file(file.bucket, file.object_key)
            qdrant_client.delete_vector(str(file_id))
            db.delete(file)
            db.commit()
            logger.info(f"🗑️ File permanently deleted: {file_id}")
        else:
            file.status = FileStatus.DELETED
            file.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"🗑️ File soft deleted: {file_id}")
        
        return True
    
    def download_file(self, db: Session, file_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get file content for download."""
        file = self.get_file(db, file_id)
        if not file:
            return None
        
        content = minio_client.download_file(file.bucket, file.object_key)
        
        return {
            'file': file,
            'content': content,
            'filename': file.filename,
            'mime_type': file.mime_type
        }
    
    def get_presigned_url(self, db: Session, file_id: uuid.UUID, expires: int = 3600) -> Optional[str]:
        """Get presigned URL for temporary access."""
        file = self.get_file(db, file_id)
        if not file:
            return None
        
        return minio_client.get_presigned_url(file.bucket, file.object_key, expires)
    
    def list_files(
        self,
        db: Session,
        department: Optional[str] = None,
        file_type: Optional[str] = None,
        uploaded_by: Optional[int] = None,
        status: str = FileStatus.ACTIVE,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List files with filters."""
        query = db.query(File).filter(File.status == status)
        
        if department:
            query = query.filter(File.department == department)
        if file_type:
            query = query.filter(File.file_type == file_type)
        if uploaded_by:
            query = query.filter(File.uploaded_by == uploaded_by)
        
        total = query.count()
        files = query.order_by(File.created_at.desc()).offset(offset).limit(limit).all()
        
        return {
            'total': total,
            'files': files,
            'limit': limit,
            'offset': offset
        }
    
    def create_version(
        self,
        db: Session,
        file_id: uuid.UUID,
        content: bytes,
        uploaded_by: User,
        change_description: Optional[str] = None
    ) -> Optional[File]:
        """Create a new version of a file."""
        file = self.get_file(db, file_id)
        if not file:
            return None
        
        try:
            new_version = file.version + 1
            new_object_key = f"{file_id}/v{new_version}_{file.filename}"
            
            minio_client.upload_file(
                bucket=file.bucket,
                object_key=new_object_key,
                file_data=content,
                content_type=file.mime_type
            )
            
            file.is_latest = False
            file.updated_at = datetime.utcnow()
            
            version_record = FileVersion(
                file_id=file_id,
                version_number=new_version,
                bucket=file.bucket,
                object_key=new_object_key,
                file_size=len(content),
                change_description=change_description,
                uploaded_by=uploaded_by.id
            )
            db.add(version_record)
            
            file.object_key = new_object_key
            file.file_size = len(content)
            file.version = new_version
            file.is_latest = True
            file.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(file)
            
            # Update embedding
            extracted_text = text_extractor.extract_text_for_embedding(
                file_path=file.filename,
                content=content
            )
            
            if extracted_text:
                vector = embedding_service.embed_text(extracted_text)
                if vector:
                    qdrant_client.upsert_vector(
                        file_id=str(file_id),
                        vector=vector,
                        payload={
                            "file_id": str(file_id),
                            "file_type": file.file_type,
                            "department": file.department,
                            "uploaded_by": str(file.uploaded_by) if file.uploaded_by else None,
                            "title": file.title,
                            "version": new_version,
                            "created_at": file.created_at.isoformat() if file.created_at else None
                        }
                    )
            
            logger.info(f"✅ New version created: {file_id} v{new_version}")
            return file
            
        except Exception as e:
            logger.error(f"❌ Version creation failed: {str(e)}")
            db.rollback()
            return None
    
    def get_file_statistics(self, db: Session, department: Optional[str] = None) -> Dict[str, Any]:
        """Get file statistics."""
        query = db.query(File).filter(File.status == FileStatus.ACTIVE)
        
        if department:
            query = query.filter(File.department == department)
        
        total_files = query.count()
        total_size = query.with_entities(db.func.sum(File.file_size)).scalar() or 0
        
        from sqlalchemy import func
        by_type = db.query(
            File.file_type,
            func.count(File.id).label('count')
        ).filter(File.status == FileStatus.ACTIVE)
        
        if department:
            by_type = by_type.filter(File.department == department)
        
        by_type = by_type.group_by(File.file_type).all()
        by_type_dict = {row[0]: row[1] for row in by_type}
        
        return {
            'total_files': total_files,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'by_type': by_type_dict
        }


# Singleton instance
file_service = FileService()
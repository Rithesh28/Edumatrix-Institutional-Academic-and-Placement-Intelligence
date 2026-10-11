"""
MinIO Client for File Storage Service

Handles all MinIO operations:
- Upload files
- Download files
- Delete files
- Generate presigned URLs
- Create buckets
- Check bucket existence
"""

import os
import logging
from io import BytesIO
from typing import Optional, BinaryIO, List
from minio import Minio
from minio.error import S3Error
from fastapi import UploadFile

from ...core.config import settings

logger = logging.getLogger(__name__)


class MinIOClient:
    """
    MinIO client wrapper for file operations.
    """
    
    def __init__(self):
        self.buckets = settings.MINIO_BUCKETS
        self._buckets_checked = False
        try:
            self.client = Minio(
                endpoint=f"{settings.MINIO_HOST}:{settings.MINIO_PORT}",
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
            logger.info(f"✅ MinIO client initialized for {settings.MINIO_HOST}:{settings.MINIO_PORT}")
        except Exception as e:
            self.client = None
            logger.warning(f"⚠️ MinIO client initialization failed: {e}")
    
    def ensure_buckets(self):
        """Create all required buckets if they don't exist."""
        if not self.client or self._buckets_checked:
            return
        try:
            for bucket in self.buckets:
                self._create_bucket_if_not_exists(bucket)
            self._buckets_checked = True
            logger.info(f"✅ All buckets verified: {', '.join(self.buckets)}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to ensure buckets: {str(e)}")
    
    def _create_bucket_if_not_exists(self, bucket_name: str):
        """Create a bucket if it doesn't exist."""
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"📁 Created bucket: {bucket_name}")
            else:
                logger.debug(f"📁 Bucket already exists: {bucket_name}")
        except S3Error as e:
            logger.error(f"❌ Failed to create bucket {bucket_name}: {str(e)}")
            raise
    
    def upload_file(
        self,
        bucket: str,
        object_key: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> str:
        """
        Upload a file to MinIO.
        
        Args:
            bucket: Bucket name
            object_key: Object key (path in bucket)
            file_data: File content as bytes
            content_type: MIME type
            metadata: Additional metadata
            
        Returns:
            object_key: The key of the uploaded object
        """
        try:
            self._create_bucket_if_not_exists(bucket)
            file_size = len(file_data)
            file_stream = BytesIO(file_data)
            
            self.client.put_object(
                bucket_name=bucket,
                object_name=object_key,
                data=file_stream,
                length=file_size,
                content_type=content_type,
                metadata=metadata or {}
            )
            
            logger.info(f"📤 Uploaded: {bucket}/{object_key} ({file_size} bytes)")
            return object_key
            
        except S3Error as e:
            logger.error(f"❌ Upload failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Upload failed: {str(e)}")
            raise
    
    def upload_file_from_path(
        self,
        bucket: str,
        object_key: str,
        file_path: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Upload a file from local path to MinIO.
        
        Args:
            bucket: Bucket name
            object_key: Object key (path in bucket)
            file_path: Local file path
            content_type: MIME type (auto-detected if not provided)
            metadata: Additional metadata
            
        Returns:
            object_key: The key of the uploaded object
        """
        try:
            with open(file_path, 'rb') as file:
                file_data = file.read()
            
            # Detect content type if not provided
            if not content_type:
                import mimetypes
                content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            
            return self.upload_file(bucket, object_key, file_data, content_type, metadata)
            
        except Exception as e:
            logger.error(f"❌ Upload from path failed: {str(e)}")
            raise
    
    def download_file(self, bucket: str, object_key: str) -> bytes:
        """
        Download a file from MinIO.
        
        Args:
            bucket: Bucket name
            object_key: Object key (path in bucket)
            
        Returns:
            bytes: File content
        """
        try:
            response = self.client.get_object(bucket, object_key)
            data = response.read()
            response.close()
            response.release_conn()
            
            logger.info(f"📥 Downloaded: {bucket}/{object_key} ({len(data)} bytes)")
            return data
            
        except S3Error as e:
            logger.error(f"❌ Download failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Download failed: {str(e)}")
            raise
    
    def delete_file(self, bucket: str, object_key: str) -> bool:
        """
        Delete a file from MinIO.
        
        Args:
            bucket: Bucket name
            object_key: Object key (path in bucket)
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            self.client.remove_object(bucket, object_key)
            logger.info(f"🗑️ Deleted: {bucket}/{object_key}")
            return True
            
        except S3Error as e:
            logger.error(f"❌ Delete failed: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Delete failed: {str(e)}")
            return False
    
    def get_presigned_url(
        self,
        bucket: str,
        object_key: str,
        expires: int = 3600
    ) -> str:
        """
        Generate a presigned URL for temporary access.
        
        Args:
            bucket: Bucket name
            object_key: Object key (path in bucket)
            expires: Expiry time in seconds (default: 1 hour)
            
        Returns:
            str: Presigned URL
        """
        try:
            # Convert expires to timedelta for compatibility
            from datetime import timedelta
            expiry = timedelta(seconds=expires)
            
            url = self.client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_key,
                expires=expiry
            )
            logger.info(f"🔗 Generated presigned URL for: {bucket}/{object_key}")
            return url
            
        except Exception as e:
            logger.error(f"❌ Presigned URL generation failed: {str(e)}")
            raise
    
    def get_object_info(self, bucket: str, object_key: str) -> Optional[dict]:
        """
        Get object metadata.
        
        Args:
            bucket: Bucket name
            object_key: Object key (path in bucket)
            
        Returns:
            dict: Object metadata or None if not found
        """
        try:
            stat = self.client.stat_object(bucket, object_key)
            return {
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "metadata": stat.metadata
            }
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.warning(f"⚠️ Object not found: {bucket}/{object_key}")
                return None
            logger.error(f"❌ Object info failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Object info failed: {str(e)}")
            return None
    
    def list_objects(
        self,
        bucket: str,
        prefix: Optional[str] = None,
        recursive: bool = True
    ) -> List[dict]:
        """
        List objects in a bucket.
        
        Args:
            bucket: Bucket name
            prefix: Prefix filter
            recursive: Whether to list recursively
            
        Returns:
            List[dict]: List of object metadata
        """
        try:
            objects = []
            for obj in self.client.list_objects(bucket, prefix=prefix, recursive=recursive):
                objects.append({
                    "key": obj.object_name,
                    "size": obj.size,
                    "etag": obj.etag,
                    "last_modified": obj.last_modified
                })
            
            logger.info(f"📋 Listed {len(objects)} objects in {bucket}")
            return objects
            
        except S3Error as e:
            logger.error(f"❌ List objects failed: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"❌ List objects failed: {str(e)}")
            return []
    
    def get_bucket_usage(self, bucket: str) -> dict:
        """
        Get bucket usage statistics.
        
        Args:
            bucket: Bucket name
            
        Returns:
            dict: Usage statistics
        """
        try:
            objects = self.list_objects(bucket)
            total_size = sum(obj["size"] for obj in objects)
            
            return {
                "bucket": bucket,
                "total_objects": len(objects),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get bucket usage: {str(e)}")
            return {}


# Singleton instance
minio_client = MinIOClient()
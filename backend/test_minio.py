"""
Test script to verify MinIO client and bucket creation
"""

import logging
from app.services.file_storage.minio_client import minio_client

logging.basicConfig(level=logging.INFO)

def test_minio():
    """Test MinIO client."""
    
    print("=" * 50)
    print("Testing MinIO Client")
    print("=" * 50)
    
    # 1. Check if client is connected
    if minio_client.client:
        print("✅ MinIO client connected")
    else:
        print("❌ MinIO client not connected")
        return
    
    # 2. List all buckets
    print("\n📁 Buckets:")
    for bucket in minio_client.buckets:
        print(f"   - {bucket}")
    
    # 3. Get usage for each bucket
    print("\n📊 Usage:")
    for bucket in minio_client.buckets:
        usage = minio_client.get_bucket_usage(bucket)
        print(f"   {bucket}: {usage.get('total_objects', 0)} objects, "
              f"{usage.get('total_size_mb', 0):.2f} MB")
    
    # 4. Test upload
    test_content = b"Hello, this is a test file for MinIO!"
    test_key = "test/test_file.txt"
    
    try:
        minio_client.upload_file(
            bucket="circulars",
            object_key=test_key,
            file_data=test_content,
            content_type="text/plain"
        )
        print(f"\n✅ Uploaded test file: circulars/{test_key}")
        
        # Download test
        downloaded = minio_client.download_file("circulars", test_key)
        if downloaded == test_content:
            print("✅ Download verified")
        
        # Get presigned URL
        url = minio_client.get_presigned_url("circulars", test_key)
        print(f"🔗 Presigned URL: {url[:50]}...")
        
        # Clean up
        minio_client.delete_file("circulars", test_key)
        print("🗑️ Test file cleaned up")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
    
    print("\n" + "=" * 50)
    print("Test complete!")
    print("=" * 50)


if __name__ == "__main__":
    test_minio()
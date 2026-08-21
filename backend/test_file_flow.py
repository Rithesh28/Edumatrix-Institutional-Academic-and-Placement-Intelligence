"""
Complete file upload flow test
"""

import requests
import json
import os
import sys

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTUsImVtYWlsIjoiYWRtaW5AZWR1bWF0cml4LmNvbSIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc4Njk3MjU4OX0.9z2xIK3z3laeBktglbTOCqNemdnerrbIah_75WBqBDQ'
BASE_URL = 'http://localhost:8000'
headers = {'Authorization': f'Bearer {TOKEN}'}
FILE_ID = '3416ee19-24ea-41f3-b5cd-a31eeef57483'

def test_search():
    """Test search functionality."""
    print('=' * 60)
    print('Testing Search')
    print('=' * 60)
    
    search_data = {
        'query': 'exam duty test',
        'limit': 10,
        'department': 'CS'
    }
    
    print('\n🔍 Searching for: exam duty test')
    response = requests.post(f'{BASE_URL}/files/search', headers=headers, json=search_data)
    
    if response.status_code == 200:
        results = response.json()
        print(f'✅ Found {results.get("total")} results')
        for result in results.get('results', []):
            print(f'   - {result.get("title")} (Score: {result.get("score", 0):.4f})')
            print(f'     File ID: {result.get("file_id")}')
            print(f'     Type: {result.get("file_type")}')
    else:
        print(f'❌ Search failed: {response.text}')

def test_download():
    """Test download functionality."""
    print('\n' + '=' * 60)
    print('Testing Download')
    print('=' * 60)
    
    print(f'\n📥 Downloading file: {FILE_ID}')
    response = requests.get(f'{BASE_URL}/files/{FILE_ID}/download', headers=headers)
    
    if response.status_code == 200:
        print(f'✅ Download successful!')
        print(f'   Size: {len(response.content)} bytes')
        print(f'   Content-Type: {response.headers.get("content-type")}')
        
        # Save the file
        with open('/tmp/downloaded_file.png', 'wb') as f:
            f.write(response.content)
        print('   Saved to: /tmp/downloaded_file.png')
    else:
        print(f'❌ Download failed: {response.text}')

def test_file_details():
    """Test getting file details."""
    print('\n' + '=' * 60)
    print('File Details')
    print('=' * 60)
    
    response = requests.get(f'{BASE_URL}/files/{FILE_ID}', headers=headers)
    
    if response.status_code == 200:
        file_data = response.json()
        print(f'\n📄 File: {file_data.get("filename")}')
        print(f'   ID: {file_data.get("id")}')
        print(f'   Title: {file_data.get("title")}')
        print(f'   Size: {file_data.get("file_size")} bytes')
        print(f'   Type: {file_data.get("file_type")}')
        print(f'   Department: {file_data.get("department")}')
        print(f'   Status: {file_data.get("status")}')
        print(f'   MIME Type: {file_data.get("mime_type")}')
        print(f'   Created: {file_data.get("created_at")}')
        print(f'   Bucket: {file_data.get("bucket")}')
        print(f'   Object Key: {file_data.get("object_key")}')
    else:
        print(f'❌ Failed: {response.text}')

def test_statistics():
    """Test statistics."""
    print('\n' + '=' * 60)
    print('File Statistics')
    print('=' * 60)
    
    response = requests.get(f'{BASE_URL}/files/stats', headers=headers)
    
    if response.status_code == 200:
        stats = response.json()
        print(f'\n📊 Total Files: {stats.get("total_files")}')
        print(f'   Total Size: {stats.get("total_size_mb")} MB')
        print(f'   By Type:')
        for file_type, count in stats.get('by_type', {}).items():
            print(f'      - {file_type}: {count}')
        print(f'\n   Recent Uploads:')
        for file in stats.get('recent_uploads', []):
            print(f'      - {file.get("title")} ({file.get("file_type")})')
    else:
        print(f'❌ Failed: {response.text}')

def test_minio():
    """Test MinIO storage."""
    print('\n' + '=' * 60)
    print('MinIO Storage Check')
    print('=' * 60)
    
    from app.services.file_storage.minio_client import minio_client
    objects = minio_client.list_objects('exam-duties')
    
    print(f'\n📁 exam-duties bucket:')
    if objects:
        for obj in objects:
            print(f'   - {obj["key"]} ({obj["size"]} bytes)')
            print(f'     Last Modified: {obj.get("last_modified")}')
    else:
        print('   (empty)')

def test_qdrant():
    """Test Qdrant vector database."""
    print('\n' + '=' * 60)
    print('Qdrant Vector Database Check')
    print('=' * 60)
    
    from app.services.file_storage.qdrant_client import qdrant_client
    
    info = qdrant_client.get_collection_info()
    print(f'\n📊 Collection: {info.get("name")}')
    print(f'   Points: {info.get("points_count")}')
    print(f'   Vector Size: {info.get("vector_size")}')
    print(f'   Distance: {info.get("distance")}')
    
    if info.get('points_count', 0) > 0:
        print('\n📋 Stored vectors:')
        result = qdrant_client.search(
            query_vector=[0.0] * 384,
            limit=5
        )
        for r in result:
            print(f'   - File ID: {r.get("payload", {}).get("file_id")}')
            print(f'     Score: {r.get("score"):.4f}')
            print(f'     Title: {r.get("payload", {}).get("title")}')

def main():
    """Run all tests."""
    test_search()
    test_file_details()
    test_download()
    test_statistics()
    test_minio()
    test_qdrant()
    
    print('\n' + '=' * 60)
    print('All tests complete!')
    print('=' * 60)

if __name__ == "__main__":
    main()
from app.core.database import SessionLocal
from app.models.circular import Circular
from app.models.file import File, FileStatus

db = SessionLocal()

# Get the CIE timetable circular
circular = db.query(Circular).filter(Circular.id == 132).first()
if circular:
    content = circular.content or ""
    print(f'Circular ID: {circular.id}')
    print(f'Title: {circular.title}')
    print(f'Content length: {len(content)}')
    print(f'Content preview: {content[:1000]}')
    print()

# Get the file record
file_record = db.query(File).filter(File.id == '460a766e-4a86-479e-b263-f47e363d44c3').first()
if file_record:
    print(f'File ID: {file_record.id}')
    print(f'Filename: {file_record.filename}')
    print(f'File type: {file_record.file_type}')
    print(f'Status: {file_record.status}')
    print(f'Bucket: {file_record.bucket}')
    print(f'Object key: {file_record.object_key}')

db.close()
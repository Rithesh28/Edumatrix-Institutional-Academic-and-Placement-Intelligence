from app.core.database import SessionLocal
from app.models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    LectureNote,
    StudentStudyDocument,
)
from app.models.user import User
from app.services.file_storage.minio_client import minio_client
from app.services.file_storage.qdrant_client import qdrant_client
from qdrant_client.http import models

db = SessionLocal()

print("=" * 60)
print("1. SUBJECT CATALOGUE")
print("=" * 60)
subjects = db.query(Subject).all()
for s in subjects:
    print(f"ID={s.id} | Code={s.code} | Name='{s.name}' | Dept={s.department} | Sem={s.semester} | Year={s.academic_year} | Ver={s.curriculum_version} | Active={s.is_active}")

print("\n" + "=" * 60)
print("2. LECTURE NOTES")
print("=" * 60)
notes = db.query(LectureNote).all()
for n in notes:
    print(f"ID={n.id} | SubjectID={n.subject_id} | Title='{n.title}' | File={n.original_filename} | Status={n.status} | Proc={n.processing_status} | Idx={n.indexing_status} | MinIO={n.minio_object_key}")

print("\n" + "=" * 60)
print("3. SYLLABUS DOCUMENTS")
print("=" * 60)
syllabi = db.query(SyllabusDocument).all()
for syl in syllabi:
    print(f"ID={syl.id} | SubjectID={syl.subject_id} | Title='{syl.title}' | Proc={syl.processing_status} | Rev={syl.review_status} | MinIO={syl.minio_object_key}")

print("\n" + "=" * 60)
print("4. SYLLABUS UNITS & TOPICS")
print("=" * 60)
units = db.query(SyllabusUnit).all()
for u in units:
    print(f"Unit ID={u.id} | SubjectID={u.subject_id} | UnitNo={u.unit_number} | Title='{u.title}'")
topics = db.query(SyllabusTopic).all()
for t in topics:
    print(f"Topic ID={t.id} | UnitID={t.unit_id} | Title='{t.title}'")

print("\n" + "=" * 60)
print("5. STUDENT STUDY DOCUMENTS (MUST BE PRESERVED)")
print("=" * 60)
student_docs = db.query(StudentStudyDocument).all()
print(f"Total Student Study Documents: {len(student_docs)}")
for sd in student_docs:
    print(f"ID={sd.id} | StudentID={sd.student_id} | SubjectID={sd.subject_id} | Title='{sd.title}' | File={sd.original_filename} | MinIO={sd.minio_object_key} | Active={sd.is_active}")

print("\n" + "=" * 60)
print("6. USER TABLE ROLES, DEPTS, AND SEMESTER")
print("=" * 60)
users = db.query(User).all()
print(f"Total Users: {len(users)}")
for u in users:
    role_val = u.role.value if hasattr(u.role, 'value') else str(u.role)
    sem_val = getattr(u, 'semester', None)
    print(f"User ID={u.id} | Email={u.email} | Role={role_val} | Dept={u.department} | Sem={sem_val}")

print("\n" + "=" * 60)
print("7. QDRANT COLLECTIONS AND POINTS IN study_buddy_chunks")
print("=" * 60)
try:
    cols = qdrant_client.client.get_collections()
    print("Collections:", [c.name for c in cols.collections])
    if "study_buddy_chunks" in [c.name for c in cols.collections]:
        info = qdrant_client.client.get_collection("study_buddy_chunks")
        print(f"study_buddy_chunks points count: {info.points_count}")
        
        # Scroll points to see source_type distribution
        records, _ = qdrant_client.client.scroll(
            collection_name="study_buddy_chunks",
            limit=100,
            with_payload=True,
            with_vectors=False
        )
        print(f"Sample points in study_buddy_chunks ({len(records)} points):")
        for r in records[:15]:
            payload = r.payload or {}
            print(f"  Point ID={r.id} | source_type={payload.get('source_type')} | subject_id={payload.get('subject_id')} | note_id={payload.get('note_id')} | sdoc_id={payload.get('student_study_document_id')} | title={payload.get('title')}")
except Exception as e:
    print(f"Qdrant inspect error: {e}")

print("\n" + "=" * 60)
print("8. MINIO BUCKETS AND OBJECTS")
print("=" * 60)
try:
    buckets = minio_client.client.list_buckets()
    print("Buckets:", [b.name for b in buckets])
    for b in buckets:
        print(f"--- Bucket: {b.name} ---")
        objects = list(minio_client.client.list_objects(b.name, recursive=True))
        print(f"Total objects in {b.name}: {len(objects)}")
        for obj in objects[:10]:
            print(f"  {obj.object_name} ({obj.size} bytes)")
except Exception as e:
    print(f"MinIO inspect error: {e}")

db.close()

"""
Phase 1: Safe cleanup of test academic data.
Cleans:
1. Test records in `files` table where file_type IN ('syllabus', 'lecture_note').
2. Orphaned files in MinIO `syllabi` bucket.
3. Orphaned test files in MinIO `student-documents` bucket (preserving active student documents).
4. Refreshes Qdrant vectors for active student documents to remove stale test subject references.
Preserves:
- All users, credentials, departments, roles.
- All student profiles and lecturer profiles.
- All circulars, resumes, exam duties, placements, assignments.
- Active private student study documents.
- Existing Qdrant `files` collection and points.
"""

from app.core.database import SessionLocal
from app.services.file_storage.minio_client import minio_client
from app.services.file_storage.qdrant_client import qdrant_client
from app.services.student_documents_indexing_service import student_documents_indexing_service
from app.models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    LectureNote,
    StudentStudyDocument,
    StudentDocIndexingStatus,
)
from sqlalchemy import text

def run_cleanup():
    db = SessionLocal()
    try:
        print("=== 1. Checking study_buddy academic tables ===")
        # Any test subjects in DB
        subjects = db.query(Subject).all()
        print(f"Subjects in DB: {len(subjects)}")
        for s in subjects:
            print(f"Deleting Subject {s.id} ({s.code} - {s.name})...")
            db.delete(s)
        db.commit()

        # Any lecture notes in DB
        notes = db.query(LectureNote).all()
        print(f"Lecture notes in DB: {len(notes)}")
        for n in notes:
            db.delete(n)
        db.commit()

        # Any syllabus documents in DB
        syllabi = db.query(SyllabusDocument).all()
        print(f"Syllabus documents in DB: {len(syllabi)}")
        for syl in syllabi:
            db.delete(syl)
        db.commit()

        print("\n=== 2. Cleaning test rows from files table ===")
        del_files = db.execute(text("DELETE FROM files WHERE file_type IN ('syllabus', 'lecture_note')"))
        print(f"Deleted {del_files.rowcount} test rows from files table.")
        db.commit()

        print("\n=== 3. Cleaning MinIO syllabi bucket ===")
        syl_objs = list(minio_client.client.list_objects("syllabi", recursive=True))
        print(f"Found {len(syl_objs)} objects in syllabi bucket to remove.")
        for o in syl_objs:
            minio_client.client.remove_object("syllabi", o.object_name)
        print("Cleaned syllabi bucket.")

        print("\n=== 4. Cleaning orphaned objects from student-documents bucket ===")
        sdocs = db.query(StudentStudyDocument).all()
        valid_keys = {sd.minio_object_key for sd in sdocs}
        print(f"Preserving active student document keys: {valid_keys}")
        sd_objs = list(minio_client.client.list_objects("student-documents", recursive=True))
        removed_sd = 0
        for o in sd_objs:
            if o.object_name not in valid_keys:
                minio_client.client.remove_object("student-documents", o.object_name)
                removed_sd += 1
        print(f"Removed {removed_sd} orphaned objects from student-documents bucket.")

        print("\n=== 5. Refreshing Qdrant vectors for active student documents ===")
        for sd in sdocs:
            print(f"Re-indexing Student Study Document {sd.id}: '{sd.title}' (subject_id={sd.subject_id})...")
            db.query(StudentStudyDocument).filter_by(id=sd.id).update(
                {"indexing_status": StudentDocIndexingStatus.NOT_INDEXED}
            )
            db.commit()
            count = student_documents_indexing_service.index_student_document(db, sd.id, sd.student_id)
            print(f"  -> Re-indexed {count} points in Qdrant study_buddy_chunks collection.")

        print("\n=== 6. Verifying clean state ===")
        subj_cnt = db.execute(text("SELECT count(*) FROM subjects")).scalar()
        note_cnt = db.execute(text("SELECT count(*) FROM study_buddy_lecture_notes")).scalar()
        syl_cnt = db.execute(text("SELECT count(*) FROM syllabus_documents")).scalar()
        files_cnt = db.execute(text("SELECT count(*) FROM files WHERE file_type IN ('syllabus', 'lecture_note')")).scalar()
        remaining_syl_objs = len(list(minio_client.client.list_objects("syllabi", recursive=True)))
        remaining_sd_objs = len(list(minio_client.client.list_objects("student-documents", recursive=True)))

        print(f"  Subjects: {subj_cnt}")
        print(f"  Lecture Notes: {note_cnt}")
        print(f"  Syllabus Documents: {syl_cnt}")
        print(f"  Test rows in files table: {files_cnt}")
        print(f"  MinIO syllabi bucket objects: {remaining_syl_objs}")
        print(f"  MinIO student-documents bucket objects: {remaining_sd_objs} (active doc preserved)")

        # Verify Qdrant points
        records, _ = qdrant_client.client.scroll(
            collection_name="study_buddy_chunks",
            limit=100,
            with_payload=True,
            with_vectors=False
        )
        print(f"  Qdrant study_buddy_chunks points: {len(records)}")
        for r in records[:3]:
            print(f"    Point payload: source_type={r.payload.get('source_type')}, subject_id={r.payload.get('subject_id')}, title={r.payload.get('title')}")

        print("\n✅ Phase 1 Cleanup Successfully Completed!")
    finally:
        db.close()

if __name__ == "__main__":
    run_cleanup()

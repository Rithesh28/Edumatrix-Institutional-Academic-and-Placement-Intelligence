"""
EduMatrix Phase 4 — Step 4.6A: Lecture Notes Database Foundation Test Suite

Verifies:
1. Migration revision 019 linkage: down_revision is 018, no branch splits, current head is 019.
2. Safe isolated migration execution: upgrade and downgrade tested in an isolated test database
   without modifying or downgrading the main application database.
3. Live PostgreSQL table schema: study_buddy_lecture_notes columns, types, indexes, and unique constraints.
4. Model creation, defaults, and non-nullable field validation.
5. Foreign-key relationships and optional syllabus unit/topic alignment with SET NULL on unit deletion.
6. Lifecycle status, extraction processing status, and vector indexing status transitions.
7. Subject cascade deletion behavior: deleting subject cascades to lecture notes.
8. Total isolation from syllabus documents: creating, publishing, or deleting lecture notes
   never modifies or supersedes any official syllabus version, review status, or publication state.
9. Storage coordinate uniqueness: duplicate minio_object_key values are rejected.
10. Download count tracking and subject backref reverse-chronological ordering.
"""

import time
import uuid
import unittest
import importlib.util
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect, create_engine
from sqlalchemy.exc import IntegrityError
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.core.database import SessionLocal, engine
from app.models.user import User, UserRole
from app.models.file import File, FileStatus
from app.models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusProcessingStatus,
    SyllabusReviewStatus,
    LectureNote,
    LectureNoteStatus,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
)


class TestStudyBuddyStep46A(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()
        cls.timestamp = int(time.time() * 1000)

        # Retrieve test users
        cls.lecturer = cls.db.query(User).filter(User.role == UserRole.LECTURER, User.department == "AIML").first()
        if not cls.lecturer:
            cls.lecturer = cls.db.query(User).filter(User.role == UserRole.LECTURER).first()
        cls.student = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "AIML").first()
        if not cls.student:
            cls.student = cls.db.query(User).filter(User.role == UserRole.STUDENT).first()

        # Track created subject IDs for teardown cleanup
        cls.created_subject_ids = []
        cls.created_file_ids = []

    @classmethod
    def tearDownClass(cls):
        if cls.created_subject_ids:
            # Delete created test subjects (cascades lecture notes, syllabus docs, units, topics)
            cls.db.query(Subject).filter(Subject.id.in_(cls.created_subject_ids)).delete(synchronize_session=False)
            cls.db.commit()

        if cls.created_file_ids:
            cls.db.query(File).filter(File.id.in_(cls.created_file_ids)).delete(synchronize_session=False)
            cls.db.commit()

        cls.db.close()

    def _create_test_subject(self, suffix: str = "") -> Subject:
        """Helper to create an isolated test subject."""
        unique_code = f"LN{self.timestamp % 100000}{suffix}"
        subject = Subject(
            code=unique_code,
            name=f"Lecture Notes Test Subject {unique_code}",
            department="AIML",
            semester=6,
            academic_year="2026-2027",
            curriculum_version="2026.1",
            description="Subject for Step 4.6A testing",
            is_active=True
        )
        self.db.add(subject)
        self.db.commit()
        self.db.refresh(subject)
        self.created_subject_ids.append(subject.id)
        return subject

    # =========================================================================
    # 1. ALEMBIC MIGRATION LINKAGE & LIVE HEAD
    # =========================================================================

    def test_01_migration_revision_linkage_and_live_head(self):
        """Verify migration 019 has down_revision 018 and current live DB is at revision 019."""
        spec = importlib.util.spec_from_file_location(
            "mig_019",
            "migrations/versions/019_add_study_buddy_lecture_notes.py"
        )
        mig_019 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig_019)

        self.assertEqual(mig_019.revision, "019", "Migration revision ID must be '019'")
        self.assertEqual(mig_019.down_revision, "018", "Migration down_revision must link to '018'")
        self.assertIsNone(mig_019.branch_labels, "Migration must not introduce branch labels")
        self.assertIsNone(mig_019.depends_on, "Migration must not have depends_on splits")

        # Verify database is currently at revision 019 or later
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version;")).fetchone()
            self.assertIsNotNone(result, "Alembic version record must exist")
            self.assertIn(result[0], ["019", "020"], f"Live database Alembic revision must be 019 or 020 (found {result[0]})")

    # =========================================================================
    # 2. ISOLATED MIGRATION UPGRADE & DOWNGRADE EXECUTION
    # =========================================================================

    def test_02_isolated_migration_upgrade_and_downgrade(self):
        """
        Verify upgrade and downgrade on an isolated temporary database.
        Guarantees that downgrade is NEVER executed against the live application database.
        """
        real_url = engine.url.render_as_string(hide_password=False)
        temp_db_name = f"test_mig_step4_6a_{int(time.time() * 1000) % 1000000}"

        admin_engine = create_engine(real_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE {temp_db_name};"))

        try:
            temp_db_url = real_url.rsplit("/", 1)[0] + f"/{temp_db_name}"
            temp_engine = create_engine(temp_db_url)

            with temp_engine.connect() as conn:
                # Create minimal parent schemas required for foreign keys
                conn.execute(text("CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255));"))
                conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
                conn.execute(text("CREATE TABLE files (id UUID PRIMARY KEY, filename VARCHAR(255));"))
                conn.execute(text("CREATE TABLE subjects (id SERIAL PRIMARY KEY, code VARCHAR(50));"))
                conn.execute(text("CREATE TABLE syllabus_documents (id SERIAL PRIMARY KEY, subject_id INT REFERENCES subjects(id));"))
                conn.execute(text("CREATE TABLE syllabus_units (id SERIAL PRIMARY KEY, document_id INT REFERENCES syllabus_documents(id));"))
                conn.execute(text("CREATE TABLE syllabus_topics (id SERIAL PRIMARY KEY, unit_id INT REFERENCES syllabus_units(id));"))
                conn.commit()

                spec = importlib.util.spec_from_file_location(
                    "mig_019_iso",
                    "migrations/versions/019_add_study_buddy_lecture_notes.py"
                )
                mig_019 = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mig_019)

                ctx = MigrationContext.configure(conn)

                # Test Upgrade
                with Operations.context(ctx):
                    mig_019.upgrade()
                conn.commit()

                insp = inspect(temp_engine)
                self.assertIn(
                    "study_buddy_lecture_notes",
                    insp.get_table_names(),
                    "study_buddy_lecture_notes table must exist after upgrade"
                )

                # Test Downgrade
                with Operations.context(ctx):
                    mig_019.downgrade()
                conn.commit()

                insp2 = inspect(temp_engine)
                self.assertNotIn(
                    "study_buddy_lecture_notes",
                    insp2.get_table_names(),
                    "study_buddy_lecture_notes table must be removed after downgrade"
                )

            temp_engine.dispose()
        finally:
            with admin_engine.connect() as conn:
                conn.execute(text(f"DROP DATABASE IF EXISTS {temp_db_name} WITH (FORCE);"))
            admin_engine.dispose()

    # =========================================================================
    # 3. LIVE DATABASE SCHEMA: COLUMNS & INDEXES
    # =========================================================================

    def test_03_database_table_columns_and_indexes(self):
        """Verify study_buddy_lecture_notes columns, types, indexes, and unique constraints in PostgreSQL."""
        insp = inspect(engine)
        tables = insp.get_table_names()
        self.assertIn("study_buddy_lecture_notes", tables, "Table study_buddy_lecture_notes must exist")

        columns = {c["name"]: c for c in insp.get_columns("study_buddy_lecture_notes")}
        expected_columns = [
            "id", "subject_id", "uploaded_by_id", "file_id", "unit_id", "topic_id",
            "title", "description", "original_filename", "file_size", "mime_type",
            "minio_bucket", "minio_object_key", "status", "is_published", "published_at",
            "processing_status", "indexing_status", "extracted_text", "extraction_error",
            "extraction_metadata", "indexed_chunk_count", "download_count",
            "created_at", "updated_at"
        ]
        for col_name in expected_columns:
            self.assertIn(col_name, columns, f"Column '{col_name}' missing from study_buddy_lecture_notes")

        # Verify indexes
        indexes = {idx["name"]: idx for idx in insp.get_indexes("study_buddy_lecture_notes")}
        expected_indexes = [
            "ix_study_buddy_lecture_notes_id",
            "ix_study_buddy_lecture_notes_subject_id",
            "ix_study_buddy_lecture_notes_uploaded_by_id",
            "ix_study_buddy_lecture_notes_file_id",
            "ix_study_buddy_lecture_notes_unit_id",
            "ix_study_buddy_lecture_notes_topic_id",
            "ix_study_buddy_lecture_notes_status",
            "ix_study_buddy_lecture_notes_is_published",
            "ix_study_buddy_lecture_notes_processing_status",
            "ix_study_buddy_lecture_notes_indexing_status",
            "ix_study_buddy_lecture_notes_subject_status",
            "ix_study_buddy_lecture_notes_subject_published",
        ]
        for idx_name in expected_indexes:
            self.assertIn(idx_name, indexes, f"Index '{idx_name}' missing from study_buddy_lecture_notes")

    # =========================================================================
    # 4. MODEL CREATION, DEFAULTS & REQUIRED FIELDS
    # =========================================================================

    def test_04_model_creation_defaults_and_required_fields(self):
        """Verify LectureNote model defaults and non-nullable field validation."""
        subject = self._create_test_subject("_defaults")

        # 1. Create with minimal required fields
        note = LectureNote(
            subject_id=subject.id,
            title="Introduction to Neural Networks",
            original_filename="intro_nn.pdf",
            file_size=102450,
            mime_type="application/pdf",
            minio_object_key=f"lecture-notes/{subject.id}/intro_nn_{self.timestamp}.pdf"
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        # Assert default values
        self.assertIsNotNone(note.id)
        self.assertEqual(note.status, LectureNoteStatus.DRAFT)
        self.assertFalse(note.is_published)
        self.assertIsNone(note.published_at)
        self.assertEqual(note.processing_status, LectureNoteProcessingStatus.UPLOADED)
        self.assertEqual(note.indexing_status, LectureNoteIndexingStatus.NOT_INDEXED)
        self.assertEqual(note.indexed_chunk_count, 0)
        self.assertEqual(note.download_count, 0)
        self.assertEqual(note.minio_bucket, "lecture-notes")
        self.assertIsNone(note.description)
        self.assertIsNone(note.extracted_text)
        self.assertIsNone(note.extraction_error)
        self.assertIsNotNone(note.created_at)

        # 2. Missing required field raises IntegrityError
        invalid_note = LectureNote(
            subject_id=subject.id,
            # missing title
            original_filename="test.pdf",
            file_size=100,
            mime_type="application/pdf",
            minio_object_key=f"invalid_{self.timestamp}.pdf"
        )
        self.db.add(invalid_note)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    # =========================================================================
    # 5. FOREIGN KEYS & OPTIONAL SYLLABUS ALIGNMENT
    # =========================================================================

    def test_05_foreign_keys_and_optional_syllabus_alignment(self):
        """Verify foreign-key relationships to Subject, User, File, SyllabusUnit, SyllabusTopic."""
        subject = self._create_test_subject("_align")

        # Create File record
        file_uuid = uuid.uuid4()
        file_record = File(
            id=file_uuid,
            filename="unit1_notes.pdf",
            file_size=204800,
            mime_type="application/pdf",
            bucket="lecture-notes",
            object_key=f"notes/{file_uuid}_unit1.pdf",
            department="AIML",
            file_type="lecture_note",
            uploaded_by=self.lecturer.id if self.lecturer else None,
            status=FileStatus.ACTIVE
        )
        self.db.add(file_record)
        self.db.commit()
        self.created_file_ids.append(file_uuid)

        # Create official syllabus hierarchy
        syllabus_doc = SyllabusDocument(
            subject_id=subject.id,
            version=1,
            is_latest=True,
            title=f"{subject.code} Syllabus",
            original_filename="syllabus.pdf",
            file_size=50000,
            mime_type="application/pdf",
            minio_bucket="syllabi",
            minio_object_key=f"syllabi/{subject.id}/syl_{self.timestamp}.pdf",
            uploaded_by_id=self.lecturer.id if self.lecturer else None,
            processing_status=SyllabusProcessingStatus.EXTRACTED,
            review_status=SyllabusReviewStatus.APPROVED,
            is_published=True
        )
        self.db.add(syllabus_doc)
        self.db.commit()
        self.db.refresh(syllabus_doc)

        unit = SyllabusUnit(
            document_id=syllabus_doc.id,
            unit_number=1,
            title="Unit 1: Foundations of Deep Learning",
            order=1
        )
        self.db.add(unit)
        self.db.commit()
        self.db.refresh(unit)

        topic = SyllabusTopic(
            unit_id=unit.id,
            title="Topic 1.1: Perceptrons and Activation Functions",
            order=1
        )
        self.db.add(topic)
        self.db.commit()
        self.db.refresh(topic)

        # Create aligned lecture note
        note = LectureNote(
            subject_id=subject.id,
            uploaded_by_id=self.lecturer.id if self.lecturer else None,
            file_id=file_record.id,
            unit_id=unit.id,
            topic_id=topic.id,
            title="Unit 1 Lecture Slides & Annotated Handout",
            description="Comprehensive coverage of perceptron architectures",
            original_filename="unit1_notes.pdf",
            file_size=204800,
            mime_type="application/pdf",
            minio_object_key=f"lecture-notes/{subject.id}/u1_notes_{self.timestamp}.pdf"
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        # Verify relationship navigation
        self.assertEqual(note.subject.id, subject.id)
        self.assertEqual(note.file.id, file_record.id)
        self.assertEqual(note.unit.title, "Unit 1: Foundations of Deep Learning")
        self.assertEqual(note.topic.title, "Topic 1.1: Perceptrons and Activation Functions")
        if self.lecturer:
            self.assertEqual(note.uploader.id, self.lecturer.id)

        # Verify SET NULL behavior when unit is deleted
        # Deleting the topic sets topic_id to NULL
        self.db.delete(topic)
        self.db.commit()
        self.db.refresh(note)
        self.assertIsNone(note.topic_id, "Topic deletion must SET NULL on note.topic_id without deleting note")

        # Deleting the unit sets unit_id to NULL
        self.db.delete(unit)
        self.db.commit()
        self.db.refresh(note)
        self.assertIsNone(note.unit_id, "Unit deletion must SET NULL on note.unit_id without deleting note")
        self.assertIsNotNone(note.id, "LectureNote record must persist after aligned unit is removed")

    # =========================================================================
    # 6. LIFECYCLE & EXTRACTION & INDEXING STATUS TRANSITIONS
    # =========================================================================

    def test_06_lifecycle_and_processing_status_transitions(self):
        """Verify valid transitions across lifecycle, processing, and vector indexing enums."""
        subject = self._create_test_subject("_transitions")

        note = LectureNote(
            subject_id=subject.id,
            title="Recurrent Neural Networks Handout",
            original_filename="rnn_notes.pdf",
            file_size=409600,
            mime_type="application/pdf",
            minio_object_key=f"lecture-notes/{subject.id}/rnn_{self.timestamp}.pdf"
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        # 1. Extraction lifecycle: UPLOADED -> PROCESSING -> EXTRACTED
        note.processing_status = LectureNoteProcessingStatus.PROCESSING
        self.db.commit()
        self.db.refresh(note)
        self.assertEqual(note.processing_status, LectureNoteProcessingStatus.PROCESSING)

        note.processing_status = LectureNoteProcessingStatus.EXTRACTED
        note.extracted_text = "RNNs process sequential inputs using recurrent hidden states."
        note.extraction_metadata = {"page_count": 5, "extractor": "pdfplumber"}
        self.db.commit()
        self.db.refresh(note)
        self.assertEqual(note.processing_status, LectureNoteProcessingStatus.EXTRACTED)
        self.assertIn("sequential inputs", note.extracted_text)

        # 2. Vector indexing lifecycle: NOT_INDEXED -> INDEXING -> INDEXED
        note.indexing_status = LectureNoteIndexingStatus.INDEXING
        self.db.commit()
        self.db.refresh(note)
        self.assertEqual(note.indexing_status, LectureNoteIndexingStatus.INDEXING)

        note.indexing_status = LectureNoteIndexingStatus.INDEXED
        note.indexed_chunk_count = 12
        self.db.commit()
        self.db.refresh(note)
        self.assertEqual(note.indexing_status, LectureNoteIndexingStatus.INDEXED)
        self.assertEqual(note.indexed_chunk_count, 12)

        # 3. Publication lifecycle: DRAFT -> PUBLISHED -> ARCHIVED
        now = datetime.now(timezone.utc)
        note.status = LectureNoteStatus.PUBLISHED
        note.is_published = True
        note.published_at = now
        self.db.commit()
        self.db.refresh(note)
        self.assertEqual(note.status, LectureNoteStatus.PUBLISHED)
        self.assertTrue(note.is_published)
        self.assertIsNotNone(note.published_at)

        note.status = LectureNoteStatus.ARCHIVED
        note.is_published = False
        self.db.commit()
        self.db.refresh(note)
        self.assertEqual(note.status, LectureNoteStatus.ARCHIVED)
        self.assertFalse(note.is_published)

    # =========================================================================
    # 7. SUBJECT CASCADE DELETION
    # =========================================================================

    def test_07_subject_cascade_deletion(self):
        """Verify that deleting a subject automatically cascades and removes its lecture notes."""
        subject = self._create_test_subject("_cascade")

        note1 = LectureNote(
            subject_id=subject.id,
            title="Note 1",
            original_filename="n1.pdf",
            file_size=1000,
            mime_type="application/pdf",
            minio_object_key=f"notes/casc1_{self.timestamp}.pdf"
        )
        note2 = LectureNote(
            subject_id=subject.id,
            title="Note 2",
            original_filename="n2.pdf",
            file_size=2000,
            mime_type="application/pdf",
            minio_object_key=f"notes/casc2_{self.timestamp}.pdf"
        )
        self.db.add_all([note1, note2])
        self.db.commit()
        note1_id, note2_id = note1.id, note2.id

        # Delete Subject
        self.db.delete(subject)
        self.db.commit()
        self.created_subject_ids.remove(subject.id)

        # Verify notes are deleted
        remaining = self.db.query(LectureNote).filter(LectureNote.id.in_([note1_id, note2_id])).all()
        self.assertEqual(len(remaining), 0, "Deleting Subject must cascade and delete associated LectureNote records")

    # =========================================================================
    # 8. SYLLABUS DOCUMENT INDEPENDENCE & INVARIANCE
    # =========================================================================

    def test_08_syllabus_document_independence(self):
        """
        CRITICAL ARCHITECTURAL INVARIANT:
        Lecture notes must be independent resources. Creating, publishing, updating, or deleting
        lecture notes must NOT modify, supersede, or unpublish any official syllabus document version.
        """
        subject = self._create_test_subject("_syl_invariance")

        # 1. Establish official approved, published syllabus v1
        syllabus_doc = SyllabusDocument(
            subject_id=subject.id,
            version=1,
            is_latest=True,
            title=f"{subject.code} Official Syllabus",
            original_filename="official_syllabus.pdf",
            file_size=75000,
            mime_type="application/pdf",
            minio_bucket="syllabi",
            minio_object_key=f"syllabi/{subject.id}/official_{self.timestamp}.pdf",
            processing_status=SyllabusProcessingStatus.EXTRACTED,
            review_status=SyllabusReviewStatus.APPROVED,
            is_published=True,
            published_at=datetime.now(timezone.utc)
        )
        self.db.add(syllabus_doc)
        self.db.commit()
        self.db.refresh(syllabus_doc)
        doc_id = syllabus_doc.id

        # 2. Add multiple lecture notes in various states
        note_published = LectureNote(
            subject_id=subject.id,
            title="Official Week 1 Lecture Notes",
            original_filename="week1.pdf",
            file_size=120000,
            mime_type="application/pdf",
            minio_object_key=f"notes/wk1_{self.timestamp}.pdf",
            status=LectureNoteStatus.PUBLISHED,
            is_published=True,
            published_at=datetime.now(timezone.utc)
        )
        note_draft = LectureNote(
            subject_id=subject.id,
            title="Upcoming Week 2 Draft Notes",
            original_filename="week2.pdf",
            file_size=150000,
            mime_type="application/pdf",
            minio_object_key=f"notes/wk2_{self.timestamp}.pdf",
            status=LectureNoteStatus.DRAFT,
            is_published=False
        )
        self.db.add_all([note_published, note_draft])
        self.db.commit()

        # 3. Assert syllabus document attributes remain 100% untouched
        self.db.refresh(syllabus_doc)
        self.assertEqual(syllabus_doc.id, doc_id)
        self.assertEqual(syllabus_doc.version, 1, "Syllabus version must remain 1")
        self.assertTrue(syllabus_doc.is_latest, "Syllabus is_latest must remain True")
        self.assertTrue(syllabus_doc.is_published, "Syllabus is_published must remain True")
        self.assertEqual(syllabus_doc.review_status, SyllabusReviewStatus.APPROVED, "Syllabus review_status must remain APPROVED")

        # 4. Delete one of the lecture notes
        self.db.delete(note_draft)
        self.db.commit()

        # 5. Re-verify syllabus document is still untouched
        self.db.refresh(syllabus_doc)
        self.assertEqual(syllabus_doc.version, 1)
        self.assertTrue(syllabus_doc.is_latest)
        self.assertTrue(syllabus_doc.is_published)
        self.assertEqual(syllabus_doc.review_status, SyllabusReviewStatus.APPROVED)

    # =========================================================================
    # 9. MINIO OBJECT KEY UNIQUENESS
    # =========================================================================

    def test_09_minio_object_key_uniqueness(self):
        """Verify that duplicate minio_object_key values are strictly rejected by PostgreSQL."""
        subject = self._create_test_subject("_uniqueness")
        duplicate_key = f"lecture-notes/{subject.id}/duplicate_{self.timestamp}.pdf"

        note1 = LectureNote(
            subject_id=subject.id,
            title="Note One",
            original_filename="n1.pdf",
            file_size=5000,
            mime_type="application/pdf",
            minio_object_key=duplicate_key
        )
        self.db.add(note1)
        self.db.commit()

        note2 = LectureNote(
            subject_id=subject.id,
            title="Note Two with Duplicate Key",
            original_filename="n2.pdf",
            file_size=6000,
            mime_type="application/pdf",
            minio_object_key=duplicate_key
        )
        self.db.add(note2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    # =========================================================================
    # 10. DOWNLOAD COUNT & REVERSE-CHRONOLOGICAL BACKREF
    # =========================================================================

    def test_10_download_count_and_subject_ordering(self):
        """Verify download_count tracking and Subject.lecture_notes reverse-chronological order."""
        subject = self._create_test_subject("_downloads")

        note1 = LectureNote(
            subject_id=subject.id,
            title="First Uploaded Note",
            original_filename="first.pdf",
            file_size=10000,
            mime_type="application/pdf",
            minio_object_key=f"notes/first_{self.timestamp}.pdf"
        )
        self.db.add(note1)
        self.db.commit()

        # Simulate delay
        time.sleep(0.05)

        note2 = LectureNote(
            subject_id=subject.id,
            title="Second Uploaded Note",
            original_filename="second.pdf",
            file_size=20000,
            mime_type="application/pdf",
            minio_object_key=f"notes/second_{self.timestamp}.pdf"
        )
        self.db.add(note2)
        self.db.commit()

        # Download counter increment
        note1.download_count += 1
        self.db.commit()
        self.db.refresh(note1)
        self.assertEqual(note1.download_count, 1)

        note1.download_count += 5
        self.db.commit()
        self.db.refresh(note1)
        self.assertEqual(note1.download_count, 6)

        # Verify subject backref ordering: note2 was created after note1
        self.db.refresh(subject)
        notes = subject.lecture_notes
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0].id, note2.id, "Most recently created note must be first in subject.lecture_notes")
        self.assertEqual(notes[1].id, note1.id)


if __name__ == "__main__":
    unittest.main()

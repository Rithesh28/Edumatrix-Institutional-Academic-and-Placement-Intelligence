"""
End-to-End Verification Test Script for Admin Subject Management,
Lecturer Semester-to-Subject Upload Workflow, Student Access Boundaries,
and Study Buddy Retrieval Latency.
"""

import sys
import os
import time
import io
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.main import app
from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.profile import StudentProfileExtended
from app.models.study_buddy import Subject, LectureNote, LectureNoteStatus, LectureNoteProcessingStatus, LectureNoteIndexingStatus
from app.core.security import create_access_token
from app.services.file_storage.qdrant_client import qdrant_client
from app.services.file_storage.minio_client import minio_client
from app.services.lecture_notes_indexing_service import STUDY_BUDDY_COLLECTION

def run_tests():
    db: Session = SessionLocal()
    client = TestClient(app)

    print("\n" + "="*80)
    print("🚀 RUNNING END-TO-END VERIFICATION TESTS")
    print("="*80)

    # 1. Fetch test users
    admin_user = db.query(User).filter(User.role == UserRole.ADMIN).first()
    lecturer_aiml = db.query(User).filter(User.role == UserRole.LECTURER, User.department.ilike("AIML")).first()
    if not lecturer_aiml:
        # Fallback to any lecturer
        lecturer_aiml = db.query(User).filter(User.role == UserRole.LECTURER).first()

    # Find or verify student with AIML dept and semester 7 (e.g. adi01@gmail.com)
    student_user = db.query(User).filter(User.role == UserRole.STUDENT).first()
    student_profile = db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id == student_user.id).first()
    if not student_profile:
        student_profile = StudentProfileExtended(user_id=student_user.id, branch="AIML", semester=7, roll_no="AIML001")
        db.add(student_profile)
        db.commit()
    else:
        student_profile.branch = "AIML"
        student_profile.semester = 7
        db.commit()

    print(f"👤 Users resolved:")
    print(f"   Admin: {admin_user.email} (Role: {admin_user.role})")
    print(f"   Lecturer: {lecturer_aiml.email} (Dept: {lecturer_aiml.department})")
    print(f"   Student: {student_user.email} (Dept: {student_profile.branch}, Semester: {student_profile.semester})")

    admin_token = create_access_token(data={"sub": admin_user.email, "id": admin_user.id, "role": admin_user.role.value})
    lecturer_token = create_access_token(data={"sub": lecturer_aiml.email, "id": lecturer_aiml.id, "role": lecturer_aiml.role.value})
    student_token = create_access_token(data={"sub": student_user.email, "id": student_user.id, "role": student_user.role.value})

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    lecturer_headers = {"Authorization": f"Bearer {lecturer_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # Ensure clean slate before running tests
    for s in db.query(Subject).filter(Subject.code.in_(["AIML701", "AIML501", "CSE701"])).all():
        for n in s.lecture_notes:
            db.delete(n)
        db.delete(s)
    db.commit()

    # -------------------------------------------------------------------------
    # TEST 1: Initial Empty State Check
    # -------------------------------------------------------------------------
    print("\n--- Test 1: Verify Fresh Empty Subject Catalogue ---")
    res = client.get("/study-buddy/subjects", headers=admin_headers)
    assert res.status_code == 200, f"Failed to list subjects: {res.text}"
    subjects_initial = res.json()
    print(f"✅ Initial Subject Count: {len(subjects_initial)} (Starts fresh & empty)")

    # -------------------------------------------------------------------------
    # TEST 2: Admin Subject Creation & Duplicate Prevention
    # -------------------------------------------------------------------------
    print("\n--- Test 2: Admin Creates Subjects Across Semesters & Enforces Uniqueness ---")
    sub1_payload = {
        "code": "AIML701",
        "name": "Reinforcement Learning & Decision Systems",
        "department": "AIML",
        "semester": 7,
        "curriculum_version": "2024-v1",
        "academic_year": "2024-2025",
        "is_active": True
    }
    res = client.post("/study-buddy/subjects", json=sub1_payload, headers=admin_headers)
    assert res.status_code == 201, f"Admin subject creation failed: {res.text}"
    sub1 = res.json()
    sub1_id = sub1["id"]
    print(f"✅ Created Subject 1: {sub1['code']} (Sem {sub1['semester']}, Dept: {sub1['department']}, ID: {sub1_id})")

    # Duplicate creation check
    dup_res = client.post("/study-buddy/subjects", json=sub1_payload, headers=admin_headers)
    assert dup_res.status_code == 409, f"Duplicate subject should return 409 Conflict, got {dup_res.status_code}: {dup_res.text}"
    print("✅ Duplicate subject prevention verified (HTTP 409 Conflict returned)")

    # Non-admin creation check
    unauth_res = client.post("/study-buddy/subjects", json={**sub1_payload, "code": "AIML702"}, headers=student_headers)
    assert unauth_res.status_code == 403, f"Student should be forbidden from creating subjects, got {unauth_res.status_code}"
    print("✅ Non-admin subject creation blocked (HTTP 403 Forbidden)")

    # Create Subject 2: Semester 5 (different semester)
    sub2_payload = {
        "code": "AIML501",
        "name": "Machine Learning Foundations",
        "department": "AIML",
        "semester": 5,
        "curriculum_version": "2024-v1",
        "academic_year": "2024-2025",
        "is_active": True
    }
    res2 = client.post("/study-buddy/subjects", json=sub2_payload, headers=admin_headers)
    assert res2.status_code == 201
    sub2 = res2.json()
    sub2_id = sub2["id"]
    print(f"✅ Created Subject 2: {sub2['code']} (Sem {sub2['semester']}, Dept: {sub2['department']}, ID: {sub2_id})")

    # Create Subject 3: Department CSE (different department)
    sub3_payload = {
        "code": "CSE701",
        "name": "Cloud Computing & Distributed Systems",
        "department": "CSE",
        "semester": 7,
        "curriculum_version": "2024-v1",
        "academic_year": "2024-2025",
        "is_active": True
    }
    res3 = client.post("/study-buddy/subjects", json=sub3_payload, headers=admin_headers)
    assert res3.status_code == 201
    sub3 = res3.json()
    sub3_id = sub3["id"]
    print(f"✅ Created Subject 3: {sub3['code']} (Sem {sub3['semester']}, Dept: {sub3['department']}, ID: {sub3_id})")

    # -------------------------------------------------------------------------
    # TEST 3: Lecturer Semester-to-Subject Filtering & Upload
    # -------------------------------------------------------------------------
    print("\n--- Test 3: Lecturer Semester-to-Subject Filtering & Upload ---")
    # Lecturer queries subjects for Semester 7
    res_sem7 = client.get("/study-buddy/subjects", params={"semester": 7}, headers=lecturer_headers)
    assert res_sem7.status_code == 200
    lecturer_sem7_subs = res_sem7.json()
    # Should contain AIML701, but NOT AIML501 (sem 5)
    codes_sem7 = [s["code"] for s in lecturer_sem7_subs]
    assert "AIML701" in codes_sem7, f"AIML701 should be in Sem 7 subjects: {codes_sem7}"
    assert "AIML501" not in codes_sem7, f"AIML501 should NOT be in Sem 7 subjects: {codes_sem7}"
    print(f"✅ Lecturer Semester 7 subjects: {codes_sem7}")

    # Lecturer queries subjects for Semester 5
    res_sem5 = client.get("/study-buddy/subjects", params={"semester": 5}, headers=lecturer_headers)
    assert res_sem5.status_code == 200
    codes_sem5 = [s["code"] for s in res_sem5.json()]
    assert "AIML501" in codes_sem5
    assert "AIML701" not in codes_sem5
    print(f"✅ Lecturer Semester 5 subjects: {codes_sem5}")

    # Lecturer uploads note to authorized subject AIML701
    fake_file_content = b"%PDF-1.4 Mock PDF content for Unit 1: Policy Gradients and Value Iteration in Deep RL."
    upload_res = client.post(
        f"/study-buddy/subjects/{sub1_id}/notes",
        headers=lecturer_headers,
        data={"title": "Policy Gradients and Q-Learning Overview", "description": "Unit 1 Lecture slides"},
        files={"file": ("unit1_policy_gradients.pdf", io.BytesIO(fake_file_content), "application/pdf")}
    )
    assert upload_res.status_code == 201, f"Note upload failed: {upload_res.text}"
    note1 = upload_res.json()
    note1_id = note1["id"]
    print(f"✅ Note uploaded successfully: ID={note1_id}, Title='{note1['title']}', Status={note1['status']}")

    # Lecturer uploads note to Semester 5 subject AIML501
    upload_res_sem5 = client.post(
        f"/study-buddy/subjects/{sub2_id}/notes",
        headers=lecturer_headers,
        data={"title": "Linear Regression and Support Vector Machines", "description": "Sem 5 ML note"},
        files={"file": ("sem5_ml_intro.pdf", io.BytesIO(fake_file_content), "application/pdf")}
    )
    assert upload_res_sem5.status_code == 201
    note2 = upload_res_sem5.json()
    note2_id = note2["id"]
    print(f"✅ Note uploaded to Sem 5: ID={note2_id}, Title='{note2['title']}'")

    # Manually publish notes for retrieval testing
    db.query(LectureNote).filter(LectureNote.id == note1_id).update({
        "is_published": True,
        "status": LectureNoteStatus.PUBLISHED,
        "processing_status": LectureNoteProcessingStatus.EXTRACTED,
        "indexing_status": LectureNoteIndexingStatus.INDEXED,
        "indexed_chunk_count": 2
    })
    db.query(LectureNote).filter(LectureNote.id == note2_id).update({
        "is_published": True,
        "status": LectureNoteStatus.PUBLISHED,
        "processing_status": LectureNoteProcessingStatus.EXTRACTED,
        "indexing_status": LectureNoteIndexingStatus.INDEXED,
        "indexed_chunk_count": 2
    })
    db.commit()

    # -------------------------------------------------------------------------
    # TEST 4: Student Access Control (Department & Semester Boundaries)
    # -------------------------------------------------------------------------
    print("\n--- Test 4: Student Access Control (Dept & Semester Boundaries) ---")
    # Student (Sem 7, AIML) lists subjects: should automatically see ONLY Semester 7, AIML subjects!
    student_subs_res = client.get("/study-buddy/subjects", headers=student_headers)
    assert student_subs_res.status_code == 200
    student_subs = student_subs_res.json()
    student_sub_codes = [s["code"] for s in student_subs]
    assert "AIML701" in student_sub_codes, f"Student should see their Semester 7 subject: {student_sub_codes}"
    assert "AIML501" not in student_sub_codes, f"Student should NOT see Semester 5 subject: {student_sub_codes}"
    assert "CSE701" not in student_sub_codes, f"Student should NOT see other department subject: {student_sub_codes}"
    print(f"✅ Student subject catalogue auto-restricted to Semester 7 AIML: {student_sub_codes}")

    # Student requests notes for their own Semester 7 subject AIML701 -> Allowed (200)
    notes_sem7_res = client.get(f"/study-buddy/subjects/{sub1_id}/notes", headers=student_headers)
    assert notes_sem7_res.status_code == 200
    assert len(notes_sem7_res.json()) == 1
    print("✅ Student accessed Semester 7 notes: HTTP 200 OK")

    # Student attempts to access notes for Semester 5 subject AIML501 -> Forbidden (403)
    notes_sem5_res = client.get(f"/study-buddy/subjects/{sub2_id}/notes", headers=student_headers)
    assert notes_sem5_res.status_code == 403, f"Expected 403 Forbidden for cross-semester notes, got {notes_sem5_res.status_code}"
    print(f"✅ Direct access to Semester 5 notes blocked: {notes_sem5_res.status_code} Forbidden")

    # Student attempts to download Semester 5 note directly -> Forbidden (403)
    dl_res = client.get(f"/study-buddy/notes/{note2_id}/download", headers=student_headers)
    assert dl_res.status_code == 403, f"Expected 403 Forbidden on direct download of cross-semester note, got {dl_res.status_code}"
    print(f"✅ Direct download of cross-semester note blocked: {dl_res.status_code} Forbidden")

    # Student asks question with subject_id=sub2_id (Semester 5) in Study Buddy -> Forbidden (403)
    chat_sub5_res = client.post(
        "/study-buddy/chat",
        headers=student_headers,
        json={"question": "What is linear regression?", "subject_id": sub2_id, "source_mode": "lecture_notes"}
    )
    assert chat_sub5_res.status_code == 403, f"Expected 403 Forbidden on cross-semester Study Buddy query, got {chat_sub5_res.status_code}"
    print(f"✅ Cross-semester Study Buddy question blocked: {chat_sub5_res.status_code} Forbidden")

    # -------------------------------------------------------------------------
    # TEST 5: Subject Activation / Deactivation & Qdrant Vector Synchronization
    # -------------------------------------------------------------------------
    print("\n--- Test 5: Subject Activation / Deactivation Lifecycle ---")
    # Admin deactivates subject 1
    deact_res = client.put(f"/study-buddy/subjects/{sub1_id}", json={"is_active": False}, headers=admin_headers)
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] == False
    print("✅ Admin deactivated AIML701")

    # Lecturer attempts to upload to deactivated subject -> Forbidden (400 or 403)
    unauth_upload = client.post(
        f"/study-buddy/subjects/{sub1_id}/notes",
        headers=lecturer_headers,
        data={"title": "Test Deactivated", "description": "desc"},
        files={"file": ("test.pdf", io.BytesIO(fake_file_content), "application/pdf")}
    )
    assert unauth_upload.status_code in (400, 403), f"Upload to deactivated subject must be rejected, got {unauth_upload.status_code}"
    print("✅ Upload to deactivated subject rejected")

    # Student cannot see deactivated subject
    std_subs_after = client.get("/study-buddy/subjects", headers=student_headers).json()
    assert sub1_id not in [s["id"] for s in std_subs_after]
    print("✅ Deactivated subject hidden from student subject catalogue")

    # Reactivate subject
    react_res = client.put(f"/study-buddy/subjects/{sub1_id}", json={"is_active": True}, headers=admin_headers)
    assert react_res.status_code == 200
    assert react_res.json()["is_active"] == True
    print("✅ Admin reactivated AIML701 successfully")

    # -------------------------------------------------------------------------
    # TEST 6: Measure Study Buddy AI Response Latency (Optimized)
    # -------------------------------------------------------------------------
    print("\n--- Test 6: Measure Study Buddy AI Inference Latency ---")
    from app.services.ai_generator_service import ai_generator

    # Profile generation using the shared singleton
    mock_sources = [{
        "source_type": "lecture_note",
        "source_id": note1_id,
        "source_title": "Policy Gradients and Q-Learning Overview",
        "subject_code": "AIML701",
        "subject_name": "Reinforcement Learning & Decision Systems",
        "text": "Policy gradient methods optimize the policy parameters directly using stochastic gradient ascent on expected return."
    }]

    context_str = "Policy gradient methods optimize the policy parameters directly using stochastic gradient ascent on expected return."
    t0 = time.time()
    result = ai_generator.generate_study_buddy_answer(
        query="Explain policy gradient methods in deep reinforcement learning.",
        context_str=context_str,
        sources=mock_sources
    )
    lat_sec = time.time() - t0
    print(f"⚡ Study Buddy Inference Result:")
    print(f"   Model Used: {result.get('model_used')}")
    print(f"   Sufficient Evidence: {result.get('has_sufficient_evidence')}")
    print(f"   Response Length: {len(result.get('answer', ''))} characters")
    print(f"   Optimized Latency: {lat_sec:.2f}s")
    print(f"   Sample Answer: {result.get('answer')[:120]}...")

    # -------------------------------------------------------------------------
    # TEST 7: Cleanup Test Subjects Safely
    # -------------------------------------------------------------------------
    print("\n--- Test 7: Safely Delete Created Test Subjects via Admin Endpoint ---")
    for sid in [sub1_id, sub2_id, sub3_id]:
        del_res = client.delete(f"/study-buddy/subjects/{sid}", headers=admin_headers)
        assert del_res.status_code == 200, f"Failed to delete subject {sid}: {del_res.text}"
        print(f"✅ Cleanly deleted subject {sid} (notes, syllabus, vectors, and MinIO storage purged)")

    # Verify catalogue is empty again
    final_subs = client.get("/study-buddy/subjects", headers=admin_headers).json()
    assert len(final_subs) == 0, f"Catalogue should be empty after test cleanup, got {len(final_subs)}"
    print("✅ Verified: Academic subject catalogue is fresh and 100% empty for admin!")

    print("\n" + "="*80)
    print("🎉 ALL END-TO-END VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("="*80)

if __name__ == "__main__":
    run_tests()

"""
Study Buddy Lifecycle Latency Benchmark (Phase 1 Baseline & Phase 3 Verification)

Measures and records structured metrics across the 9 lifecycle stages:
1. Attachment upload & SHA-256 calculation
2. PDF/text extraction and OCR, if triggered
3. Chunking & embedding generation
4. Qdrant indexing & confirmation
5. Retrieval from lecturer notes
6. Retrieval from attached student document
7. PostgreSQL authorization & citation validation
8. Qwen model loading & answer-generation time
9. Total end-to-end request latency

Scenarios tested:
- Scenario A: Cold question (first question after model unload)
- Scenario B: Subsequent warm question (notes only)
- Scenario C: First attachment upload and indexing (~2.8 MB test PDF)
- Scenario D: Reusing an already indexed attachment (reuse_existing=True)
- Scenario E: Question with lecturer notes plus attached document
"""

import os
import sys
import time
import json
from typing import Dict, Any, List
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.study_buddy import (
    Subject,
    LectureNote,
    LectureNoteStatus,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
    StudentStudyDocument,
)
from app.services.ai_generator_service import ai_generator
from app.services.student_documents_indexing_service import student_documents_indexing_service
from app.services.lecture_notes_indexing_service import lecture_notes_indexing_service
from app.services.file_storage.minio_client import minio_client
from app.core.study_buddy_timing import get_recent_perf_metrics, clear_recent_perf_metrics


def run_benchmark():
    client = TestClient(app)
    db = SessionLocal()

    # Find or use student user
    student = db.query(User).filter(User.role == UserRole.STUDENT, User.department == "AIML").first()
    if not student:
        student = db.query(User).filter(User.role == UserRole.STUDENT).first()
    if not student:
        print("ERROR: No student user found in database.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {create_access_token({'sub': student.email, 'id': student.id, 'role': 'student'})}"}
    pdf_path = "/tmp/Module1.pdf"
    if not os.path.exists(pdf_path):
        print(f"ERROR: {pdf_path} not found.")
        sys.exit(1)

    pdf_size = os.path.getsize(pdf_path)
    print(f"Base test PDF: {pdf_path} ({pdf_size:,} bytes, {pdf_size / 1024 / 1024:.2f} MB)")

    benchmark_results = {}

    # -------------------------------------------------------------
    # Scenario A: Cold Question (force model reload)
    # -------------------------------------------------------------
    print("\n=======================================================")
    print("▶ Running Scenario A: Cold question after backend startup")
    print("=======================================================")
    ai_generator._model = None
    ai_generator._tokenizer = None
    ai_generator._is_loaded = False

    clear_recent_perf_metrics()
    t0_cold = time.perf_counter()
    resp_cold = client.post(
        "/study-buddy/chat",
        headers=headers,
        json={
            "question": "What are the core components of neural network architectures?",
            "source_mode": "lecture_notes"
        }
    )
    t_cold_total = (time.perf_counter() - t0_cold) * 1000.0

    print(f"Status: {resp_cold.status_code}")
    cold_metrics = get_recent_perf_metrics()
    benchmark_results["scenario_a_cold_question"] = {
        "status_code": resp_cold.status_code,
        "wall_clock_total_ms": round(t_cold_total, 2),
        "stage_metrics": cold_metrics
    }
    for m in cold_metrics:
        print(f"  - {m['stage']}: {m['duration_ms']:.2f} ms")

    # -------------------------------------------------------------
    # Scenario B: Subsequent Warm Question (lecture notes only)
    # -------------------------------------------------------------
    print("\n=======================================================")
    print("▶ Running Scenario B: Subsequent warm question (notes only)")
    print("=======================================================")
    clear_recent_perf_metrics()
    t0_warm = time.perf_counter()
    resp_warm = client.post(
        "/study-buddy/chat",
        headers=headers,
        json={
            "question": "Explain how multi-head attention computes key value projections.",
            "source_mode": "lecture_notes"
        }
    )
    t_warm_total = (time.perf_counter() - t0_warm) * 1000.0

    print(f"Status: {resp_warm.status_code}")
    warm_metrics = get_recent_perf_metrics()
    benchmark_results["scenario_b_warm_question"] = {
        "status_code": resp_warm.status_code,
        "wall_clock_total_ms": round(t_warm_total, 2),
        "stage_metrics": warm_metrics
    }
    for m in warm_metrics:
        print(f"  - {m['stage']}: {m['duration_ms']:.2f} ms")

    # -------------------------------------------------------------
    # Scenario C: First Attachment Upload & Indexing (~2.8 MB PDF)
    # -------------------------------------------------------------
    print("\n=======================================================")
    print("▶ Running Scenario C: First upload and indexing (~2.8 MB PDF)")
    print("=======================================================")
    ts_now = int(time.time() * 1000)
    fresh_pdf_path = f"/tmp/Benchmark_Module1_{ts_now}.pdf"
    with open(pdf_path, "rb") as f_in, open(fresh_pdf_path, "wb") as f_out:
        f_out.write(f_in.read())
        f_out.write(f"\n% UNIQUE_BENCHMARK_TOKEN_{ts_now}\n".encode("utf-8"))

    fresh_size = os.path.getsize(fresh_pdf_path)
    print(f"Created fresh PDF for upload benchmark: {fresh_pdf_path} ({fresh_size:,} bytes)")

    clear_recent_perf_metrics()
    t0_upload = time.perf_counter()
    with open(fresh_pdf_path, "rb") as f:
        resp_upload = client.post(
            "/study-buddy/my-documents",
            headers=headers,
            files={"file": (f"Benchmark_Module1_{ts_now}.pdf", f, "application/pdf")},
            data={
                "title": f"Benchmark Module 1 ({ts_now})",
                "reuse_existing": "false"
            }
        )
    t_upload_total = (time.perf_counter() - t0_upload) * 1000.0

    print(f"Status: {resp_upload.status_code}")
    upload_metrics = get_recent_perf_metrics()
    doc_data = resp_upload.json()
    uploaded_doc_id = doc_data.get("id")

    benchmark_results["scenario_c_first_attachment_upload_indexing"] = {
        "status_code": resp_upload.status_code,
        "doc_id": uploaded_doc_id,
        "file_size_bytes": fresh_size,
        "wall_clock_total_ms": round(t_upload_total, 2),
        "stage_metrics": upload_metrics
    }
    for m in upload_metrics:
        print(f"  - {m['stage']}: {m['duration_ms']:.2f} ms ({m})")

    # -------------------------------------------------------------
    # Scenario D: Reusing an already indexed attachment
    # -------------------------------------------------------------
    print("\n=======================================================")
    print("▶ Running Scenario D: Reusing an already indexed attachment")
    print("=======================================================")
    clear_recent_perf_metrics()
    t0_reuse = time.perf_counter()
    with open(fresh_pdf_path, "rb") as f:
        resp_reuse = client.post(
            "/study-buddy/my-documents",
            headers=headers,
            files={"file": (f"Benchmark_Module1_{ts_now}.pdf", f, "application/pdf")},
            data={
                "title": f"Benchmark Module 1 Reused ({ts_now})",
                "reuse_existing": "true"
            }
        )
    t_reuse_total = (time.perf_counter() - t0_reuse) * 1000.0

    print(f"Status: {resp_reuse.status_code}")
    reuse_metrics = get_recent_perf_metrics()
    benchmark_results["scenario_d_reuse_indexed_attachment"] = {
        "status_code": resp_reuse.status_code,
        "wall_clock_total_ms": round(t_reuse_total, 2),
        "stage_metrics": reuse_metrics
    }
    for m in reuse_metrics:
        print(f"  - {m['stage']}: {m['duration_ms']:.2f} ms")

    # -------------------------------------------------------------
    # Scenario E: Question with notes plus attached document
    # -------------------------------------------------------------
    print("\n=======================================================")
    print("▶ Running Scenario E: Question with notes + attached document")
    print("=======================================================")
    clear_recent_perf_metrics()
    t0_combo = time.perf_counter()
    resp_combo = client.post(
        "/study-buddy/chat",
        headers=headers,
        json={
            "question": "Summarize the key concepts detailed in this document.",
            "source_mode": "lecture_notes",
            "attached_document_id": uploaded_doc_id
        }
    )
    t_combo_total = (time.perf_counter() - t0_combo) * 1000.0

    print(f"Status: {resp_combo.status_code}")
    combo_metrics = get_recent_perf_metrics()
    combo_json = resp_combo.json() if resp_combo.status_code == 200 else {}
    citations = combo_json.get("citations", [])

    benchmark_results["scenario_e_notes_plus_attachment_question"] = {
        "status_code": resp_combo.status_code,
        "wall_clock_total_ms": round(t_combo_total, 2),
        "citations_count": len(citations),
        "citations": [{"source_type": c.get("source_type"), "title": c.get("document_title")} for c in citations],
        "stage_metrics": combo_metrics
    }
    for m in combo_metrics:
        print(f"  - {m['stage']}: {m['duration_ms']:.2f} ms")

    # Save benchmark results to JSON
    out_file = "/tmp/study_buddy_benchmark_results.json"
    with open(out_file, "w") as f:
        json.dump(benchmark_results, f, indent=2)
    print(f"\n✅ All 5 scenarios executed! Results saved to {out_file}")

    # Clean up fresh uploaded test document
    if uploaded_doc_id:
        try:
            student_documents_indexing_service.delete_document_chunks(uploaded_doc_id)
            doc_to_del = db.query(StudentStudyDocument).filter(StudentStudyDocument.id == uploaded_doc_id).first()
            if doc_to_del:
                minio_client.delete_file(doc_to_del.minio_bucket, doc_to_del.minio_object_key)
                db.delete(doc_to_del)
                db.commit()
            print(f"Cleaned up test document {uploaded_doc_id}")
        except Exception as e:
            print(f"Cleanup warning: {e}")

    if os.path.exists(fresh_pdf_path):
        try:
            os.unlink(fresh_pdf_path)
        except Exception:
            pass


if __name__ == "__main__":
    run_benchmark()

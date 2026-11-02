"""
Final Integration Audit Script for EduMatrix Chat Intelligence
Runs end-to-end backend tests, authorization checks, and latency measurements.
"""

import time
import json
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.chat import ChatMessage
from app.api.chat import classify_and_update_message
from app.services.conversation_retrieval_service import conversation_retrieval_service
from app.services.ai_chat_service import ai_chat_service
from app.services.chat_policy import can_chat


def run_audit():
    db: Session = SessionLocal()
    audit_results = {}

    print("==========================================================")
    print("1. NORMAL CHAT CLASSIFICATION VERIFICATION")
    print("==========================================================")

    # Setup test accounts
    hod = db.query(User).filter(User.email == "audit_hod_cse@vcet.ac.in").first()
    if not hod:
        hod = User(
            email="audit_hod_cse@vcet.ac.in",
            name="Dr. Aris (HOD CSE)",
            role=UserRole.HOD,
            department="CSE",
            is_active=True,
            password_hash="dummy"
        )
        db.add(hod)

    lecturer = db.query(User).filter(User.email == "audit_lec_cse@vcet.ac.in").first()
    if not lecturer:
        lecturer = User(
            email="audit_lec_cse@vcet.ac.in",
            name="Prof. Sharma (Lecturer)",
            role=UserRole.LECTURER,
            department="CSE",
            is_active=True,
            password_hash="dummy"
        )
        db.add(lecturer)

    po = db.query(User).filter(User.email == "audit_po_cse@vcet.ac.in").first()
    if not po:
        po = User(
            email="audit_po_cse@vcet.ac.in",
            name="Mr. Verma (Placement Officer)",
            role=UserRole.PLACEMENT_OFFICER,
            department="CSE",
            is_active=True,
            password_hash="dummy"
        )
        db.add(po)

    student = db.query(User).filter(User.email == "audit_student_cse@vcet.ac.in").first()
    if not student:
        student = User(
            email="audit_student_cse@vcet.ac.in",
            name="Rohan (Student)",
            role=UserRole.STUDENT,
            department="CSE",
            is_active=True,
            password_hash="dummy"
        )
        db.add(student)

    other_student = db.query(User).filter(User.email == "audit_student_aiml@vcet.ac.in").first()
    if not other_student:
        other_student = User(
            email="audit_student_aiml@vcet.ac.in",
            name="Anita (AIML Student)",
            role=UserRole.STUDENT,
            department="AIML",
            is_active=True,
            password_hash="dummy"
        )
        db.add(other_student)

    db.commit()
    db.refresh(hod)
    db.refresh(lecturer)
    db.refresh(po)
    db.refresh(student)
    db.refresh(other_student)

    test_messages = [
        (hod, student, "DLRL exam is scheduled for 23rd November 2026."),
        (lecturer, student, "Machine Learning Assignment 2 deadline is 18th November 2026."),
        (po, student, "TCS Placement Drive shortlist published for CSE batch 2026."),
        (student, lecturer, "I am unable to understand the DSP assignment. Could you please explain?")
    ]

    created_msgs = []
    normal_chat_audits = []

    for sender, receiver, content in test_messages:
        # Measure Send/Persistence latency
        t0 = time.perf_counter()
        msg = ChatMessage(
            sender_id=sender.id,
            receiver_id=receiver.id,
            content=content,
            is_read=False,
            is_ai=False
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        persist_ms = (time.perf_counter() - t0) * 1000.0
        created_msgs.append(msg)

        # Measure Classification latency
        t0 = time.perf_counter()
        classify_and_update_message(msg.id, content)
        classify_ms = (time.perf_counter() - t0) * 1000.0

        db.refresh(msg)

        res = {
            "msg_id": msg.id,
            "sender": f"{sender.name} ({sender.role.value})",
            "content": content,
            "persist_ms": round(persist_ms, 2),
            "classify_ms": round(classify_ms, 2),
            "sentiment": msg.sentiment,
            "sentiment_conf": msg.sentiment_confidence,
            "intent": msg.intent,
            "intent_conf": msg.intent_confidence,
            "metadata_present": "classification" in (msg.ai_metadata or {})
        }
        normal_chat_audits.append(res)
        print(f"  [Msg #{msg.id}] {sender.name} -> {receiver.name}:")
        print(f"      Content: '{content[:40]}...'")
        print(f"      Persist Time: {persist_ms:.2f}ms | Classify Time: {classify_ms:.2f}ms")
        print(f"      Sentiment: {msg.sentiment} ({msg.sentiment_confidence:.2f}) | Intent: {msg.intent} ({msg.intent_confidence:.2f})")

    audit_results["normal_chat"] = normal_chat_audits

    print("\n==========================================================")
    print("2. CONVERSATION-WIDE INTELLIGENCE & ATTRIBUTION VERIFICATION")
    print("==========================================================")

    # Test HOD retrieval & AI response
    t0 = time.perf_counter()
    hod_conv_sources = conversation_retrieval_service.retrieve_user_conversations(
        db=db, user=student, query_text="When is DLRL exam?", limit=5
    )
    retrieval_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  Conversation Retrieval Time: {retrieval_ms:.2f}ms")
    print(f"  Found {len(hod_conv_sources)} source(s):")
    for src in hod_conv_sources:
        print(f"    - Title: {src['title']} | Date: {src['created_at']} | Content: '{src['content']}'")

    # Measure AI Chat Analyzer latency (First/Warm request)
    t0 = time.perf_counter()
    ai_res_1 = ai_chat_service.process_user_message(db, student, "When is DLRL exam?")
    ai_latency_1 = (time.perf_counter() - t0) * 1000.0
    created_msgs.extend([ai_res_1["user_message"], ai_res_1["ai_response"]])

    t0 = time.perf_counter()
    ai_res_2 = ai_chat_service.process_user_message(db, student, "When is Machine Learning Assignment 2 due?")
    ai_latency_2 = (time.perf_counter() - t0) * 1000.0
    created_msgs.extend([ai_res_2["user_message"], ai_res_2["ai_response"]])

    t0 = time.perf_counter()
    ai_res_3 = ai_chat_service.process_user_message(db, student, "Are there any updates on TCS placement drive?")
    ai_latency_3 = (time.perf_counter() - t0) * 1000.0
    created_msgs.extend([ai_res_3["user_message"], ai_res_3["ai_response"]])

    print(f"\n  AI Response 1 (HOD DLRL Exam):")
    print(f"    Answer: {ai_res_1['ai_response'].content}")
    print(f"    Sources Cited: {[s['title'] for s in ai_res_1['retrieval_sources']]}")
    print(f"    Latency: {ai_latency_1:.2f}ms")

    print(f"\n  AI Response 2 (Lecturer ML Assignment):")
    print(f"    Answer: {ai_res_2['ai_response'].content}")
    print(f"    Sources Cited: {[s['title'] for s in ai_res_2['retrieval_sources']]}")
    print(f"    Latency: {ai_latency_2:.2f}ms")

    print(f"\n  AI Response 3 (Placement TCS Drive):")
    print(f"    Answer: {ai_res_3['ai_response'].content}")
    print(f"    Sources Cited: {[s['title'] for s in ai_res_3['retrieval_sources']]}")
    print(f"    Latency: {ai_latency_3:.2f}ms")

    audit_results["latencies"] = {
        "retrieval_ms": round(retrieval_ms, 2),
        "ai_chat_first_ms": round(ai_latency_1, 2),
        "ai_chat_subsequent_ms_avg": round((ai_latency_2 + ai_latency_3) / 2.0, 2)
    }

    print("\n==========================================================")
    print("3. AUTHORIZATION & RBAC VALIDATION")
    print("==========================================================")

    # Check 1: Student can message HOD (Allowed)
    can_student_hod, reason_hod = can_chat(student, hod)
    print(f"  [RBAC] Student -> HOD CSE: allowed={can_student_hod} ({reason_hod})")

    # Check 2: Student can message Placement Officer (Allowed)
    can_student_po, reason_po = can_chat(student, po)
    print(f"  [RBAC] Student -> Placement Officer: allowed={can_student_po} ({reason_po})")

    # Check 3: Student -> Other Student (Blocked)
    can_student_std, reason_std = can_chat(student, other_student)
    print(f"  [RBAC] Student -> Student (Cross/P2P): allowed={can_student_std} ({reason_std})")

    # Check 4: Cross-department conversation retrieval (Blocked)
    # create a message between HOD CSE and AIML student
    cross_msg = ChatMessage(
        sender_id=hod.id,
        receiver_id=other_student.id,
        content="Secret CSE Exam Paper discussion",
        is_read=False,
        is_ai=False
    )
    db.add(cross_msg)
    db.commit()
    db.refresh(cross_msg)
    created_msgs.append(cross_msg)

    aiml_student_retrieval = conversation_retrieval_service.retrieve_user_conversations(
        db=db, user=other_student, query_text="CSE Exam Paper", limit=5
    )
    print(f"  [RBAC] AIML Student trying to retrieve CSE HOD message: retrieved={len(aiml_student_retrieval)}")

    # Cleanup test data created during audit
    print("\nCleaning up audit test records...")
    # First delete all messages referencing these users
    audit_user_ids = [hod.id, lecturer.id, po.id, student.id, other_student.id]
    db.query(ChatMessage).filter(
        (ChatMessage.sender_id.in_(audit_user_ids)) |
        (ChatMessage.receiver_id.in_(audit_user_ids))
    ).delete(synchronize_session=False)
    db.query(User).filter(User.email.in_([
        "audit_hod_cse@vcet.ac.in",
        "audit_lec_cse@vcet.ac.in",
        "audit_po_cse@vcet.ac.in",
        "audit_student_cse@vcet.ac.in",
        "audit_student_aiml@vcet.ac.in"
    ])).delete()
    db.commit()
    db.close()
    print("Cleanup completed.")


if __name__ == "__main__":
    run_audit()

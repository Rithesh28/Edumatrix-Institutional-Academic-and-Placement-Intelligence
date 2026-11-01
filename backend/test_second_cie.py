from app.core.database import SessionLocal
from app.services.ai_chat_service import ai_chat_service
from app.models.user import User, UserRole

db = SessionLocal()
test_student = db.query(User).filter(User.email == "test_ai_student@vcet.ac.in").first()
if not test_student:
    from app.models.user import User, UserRole
    test_student = User(
        email="test_ai_student@vcet.ac.in",
        name="AI Test Student",
        role=UserRole.STUDENT,
        department="CSE",
        is_active=True,
        password_hash="dummy_hash"
    )
    db.add(test_student)
    db.commit()
    db.refresh(test_student)

q = "When does the second CIE start?"
print(f"Q: {q}")
result = ai_chat_service.process_user_message(db, test_student, q)
print(f"Intent: {result['intent']} (conf: {result['intent_confidence']})")
print(f"Strategy: {result['retrieval_strategy']}")
print(f"Sources: {len(result['retrieval_sources'])}")
for s in result['retrieval_sources']:
    print(f"  - {s.get('title')} (due: {s.get('due_date')})")
print(f"Answer: {result['ai_response'].content}")

db.close()
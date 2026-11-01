from app.core.database import SessionLocal
from app.services.institutional_retrieval_service import institutional_retrieval_service

db = SessionLocal()
results = institutional_retrieval_service.retrieve_exam_information(db, 'When is DLRL CIE 2 exam', department='AIML', limit=5)
for r in results:
    title = r.get('title')
    cat = r.get('category')
    due = r.get('due_date')
    score = r.get('score')
    content = r.get('content', '')
    print(f'Title: {title}')
    print(f'Category: {cat}')
    print(f'Due: {due}')
    print(f'Score: {score}')
    print(f'Content: {content[:500]}')
    print('---')
db.close()
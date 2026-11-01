from app.core.database import SessionLocal
from app.services.query_router import query_router

db = SessionLocal()
query = 'When is DLRL CIE 2 exam'
intent = 'ask_exam_info'
intent_confidence = 0.3
result = query_router.execute_routing(db, intent, query, department='AIML', intent_confidence=intent_confidence)
print(f'Strategy: {result["strategy"]}')
print(f'Sources count: {result["source_count"]}')
for s in result['sources']:
    title = s.get('title')
    cat = s.get('category')
    due = s.get('due_date')
    score = s.get('score')
    content = s.get('content', '')
    print(f'  Title: {title}')
    print(f'  Category: {cat}')
    print(f'  Due: {due}')
    print(f'  Score: {score}')
    print(f'  Content: {content[:200]}')
    print('---')
db.close()
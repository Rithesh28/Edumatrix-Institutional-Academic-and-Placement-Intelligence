import sys
sys.path.insert(0, "/app")
from app.services.intent_classifier import intent_classifier

queries = [
    "Show me the circular about exam fees",
    "DSP test cases",
    "Explain DSP concepts",
    "I am confused about ML topics",
    "When is the Python Programming Assignment 1 deadline?",
    "Who is the president of India?",
    "When does the second CIE start?",
    "When is DLRL CIE 2 exam",
    "When is DLRL CIE 2?",
    "What is the deadline mentioned in the timetable?",
]

for q in queries:
    result = intent_classifier.predict(q)
    print(f"Q: {q}")
    print(f"  Intent: {result.get('intent')}, Confidence: {result.get('confidence')}")
    print()
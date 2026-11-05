"""Phase 9 Automated Testing Suite"""
import sys, os, csv, json
sys.path.insert(0, r'D:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\backend')

# Force reload
import importlib
from app.services import sentiment_analyser as sa_mod
importlib.reload(sa_mod)
from app.services import intent_classifier as ic_mod
importlib.reload(ic_mod)

passed = 0
failed = 0

def test(name, condition, detail=''):
    global passed, failed
    if condition:
        passed += 1
        print(f'  [PASS] {name}')
    else:
        failed += 1
        print(f'  [FAIL] {name}: {detail}')

# 1. Model loading tests (fresh instances)
print('--- Model Loading ---')
sa = sa_mod.SentimentAnalyser()
ir = sa.analyse('test')
test('Sentiment model loads (fresh)', sa.is_loaded)
test('Sentiment has classifier', sa.classifier is not None)

ic = ic_mod.IntentClassifier()
ir = ic.predict('test')
test('Intent model loads (fresh)', ic.is_loaded)
test('Intent has classifier', ic.classifier is not None)

# Note: importlib.reload() creates new module instances, so singleton references
# from the original import become stale. This is expected and does not affect
# production behavior (singletons are loaded on first request in production).
test('Singleton sentiment loaded', sa_mod.sentiment_analyser.is_loaded)
test('Singleton intent loaded', ic_mod.intent_classifier.is_loaded)

# 2. Inference tests
print()
print('--- Inference ---')
sr = sa_mod.sentiment_analyser.analyse('Thank you!')
test('Sentiment positive', sr['sentiment'] == 'positive', f'got {sr["sentiment"]}')
test('Sentiment confidence valid', 0 <= sr['confidence'] <= 1)
test('Sentiment has probabilities', 'probabilities' in sr)

sr2 = sa_mod.sentiment_analyser.analyse('This is terrible')
test('Sentiment negative', sr2['sentiment'] == 'negative', f'got {sr2["sentiment"]}')

sr3 = sa_mod.sentiment_analyser.analyse('When is the exam?')
test('Sentiment neutral', sr3['sentiment'] == 'neutral', f'got {sr3["sentiment"]}')

ir = ic_mod.intent_classifier.predict('When is the exam?')
test('Intent returns dict', isinstance(ir, dict))
test('Intent has intent key', 'intent' in ir)
test('Intent has confidence key', 'confidence' in ir)

# 3. Evaluation data
print()
print('--- Evaluation Data ---')
test_csv = r'D:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\evaluation\test_cases\ai_chat_analyzer_extended_test_cases.csv'
with open(test_csv, 'r') as f:
    tc = list(csv.DictReader(f))
test('Phase 7 dataset has 55 cases', len(tc) == 55, f'got {len(tc)}')
test('All cases have required fields', all('input_query' in c and 'expected_intent' in c and 'expected_sentiment' in c for c in tc))

# 4. Results files
print()
print('--- Results Files ---')
results_dir = r'D:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\evaluation\results'
phase8_files = [f for f in os.listdir(results_dir) if 'phase8' in f.lower()]
test('Phase 8 results exist', len(phase8_files) > 0)

# 5. Backend API
print()
print('--- Backend API ---')
from app.api.ai_chat_analytics import _get_latest_eval_metrics, _get_phase8_sentiment_metrics
metrics = _get_latest_eval_metrics()
test('Metrics endpoint loads', metrics is not None)
test('Metrics has intent_accuracy', 'intent_accuracy' in metrics)
test('Metrics has sentiment_accuracy', 'sentiment_accuracy' in metrics)
p8 = _get_phase8_sentiment_metrics()
test('Phase 8 metrics loads', p8 is not None)

# 6. Dataset validation
print()
print('--- Dataset Validation ---')
unseen_csv = r'D:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\evaluation\test_cases\ai_chat_analyzer_phase9_unseen.csv'
test('Unseen dataset exists', os.path.exists(unseen_csv))
with open(unseen_csv, 'r') as f:
    unseen = list(csv.DictReader(f))
test('Unseen has 60 cases', len(unseen) == 60, f'got {len(unseen)}')
test('Unseen no duplicates', len(set(c['test_case_id'] for c in unseen)) == len(unseen))

# 7. Frontend build
print()
print('--- Frontend Build ---')
dist_exists = os.path.exists(r'D:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\frontend\dist')
test('Frontend dist exists', dist_exists)

# 8. Dashboard JSX
print()
print('--- Dashboard JSX ---')
jsx_path = r'D:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\frontend\src\components\ai-chat-analytics\AIChatAnalytics.jsx'
with open(jsx_path, 'r') as f:
    jsx = f.read()
test('Phase 8 section in JSX', 'phase8_sentiment' in jsx)
test('Phase 7 accuracy display', 'phase7_accuracy' in jsx)
test('Improvement display', 'phase8_sentiment.improvement' in jsx)

# Summary
print()
print('=' * 50)
print(f'TOTAL: {passed + failed} tests | Passed: {passed} | Failed: {failed}')
print('=' * 50)

if failed > 0:
    sys.exit(1)

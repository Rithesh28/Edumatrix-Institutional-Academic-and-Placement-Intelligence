"""Quick Phase 8 sentiment evaluation on Phase 7 test dataset."""
import sys, os, json, pickle, csv
sys.path.insert(0, r'D:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\backend')

from sentence_transformers import SentenceTransformer
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

# Load Phase 8 model
model_path = r'D:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\backend\app\ml\sentiment_model_phase8'
model = SentenceTransformer(os.path.join(model_path, 'embedding_model'))

with open(os.path.join(model_path, 'classifier.pkl'), 'rb') as f:
    classifier = pickle.load(f)

with open(os.path.join(model_path, 'label_mapping.pkl'), 'rb') as f:
    mapping = pickle.load(f)

label_map = mapping['LABEL_MAP']  # {0: 'negative', 1: 'neutral', 2: 'positive'}
id_to_label = {v: k for k, v in label_map.items()}
# Reverse mapping: string label -> integer ID
label_to_id = {v: k for k, v in label_map.items()}
# Also create a simple int->string mapping
int_to_label = dict(enumerate(['negative', 'neutral', 'positive']))
print(f"Label map: {label_map}")
print(f"int_to_label: {int_to_label}")

# Load Phase 7 test cases
test_csv = r'D:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\evaluation\test_cases\ai_chat_analyzer_extended_test_cases.csv'
with open(test_csv, 'r') as f:
    reader = csv.DictReader(f)
    test_cases = list(reader)

queries = [tc['input_query'] for tc in test_cases]
expected = [tc['expected_sentiment'] for tc in test_cases]
expected_labels = [label_to_id[s] for s in expected]

print(f"\nTesting {len(queries)} cases with Phase 8 model...")
embeddings = model.encode(queries, show_progress_bar=True, batch_size=32)
predictions = classifier.predict(embeddings)
probabilities = classifier.predict_proba(embeddings)

accuracy = accuracy_score(expected_labels, predictions)
print(f"\nPhase 8 Accuracy: {accuracy*100:.2f}%")
print("\nPer-case results:")

errors = []
for i, (q, exp, pred) in enumerate(zip(queries, expected, [int_to_label[int(p)] for p in predictions])):
    correct = "PASS" if exp == pred else "FAIL"
    conf = max(probabilities[i])
    print(f"  {test_cases[i]['test_case_id']}: predicted={pred} ({conf:.3f}) - {correct}")
    if exp != pred:
        errors.append({
            "test_case_id": test_cases[i]["test_case_id"],
            "query": q,
            "expected": exp,
            "predicted": pred,
            "confidence": round(float(conf), 3)
        })

print(f"\nErrors: {len(errors)}/{len(queries)} ({len(errors)/len(queries)*100:.1f}%)")

# Classification report
print("\nClassification Report:")
print(classification_report(expected_labels, predictions, target_names=['negative', 'neutral', 'positive'], digits=4))

cm = confusion_matrix(expected_labels, predictions)
print("Confusion Matrix:")
print(cm)

# Compare with Phase 7
print('\n=== COMPARISON ===')
print(f'Phase 7 Accuracy: 81.82%')
print(f'Phase 8 Accuracy: {accuracy*100:.2f}%')
print(f'Change: {accuracy*100 - 81.82:+.2f}%')

# Save results
results_dir = r'D:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\evaluation\results'
os.makedirs(results_dir, exist_ok=True)
import datetime
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

results = {
    "phase": 8,
    "total_cases": len(queries),
    "correct": sum(1 for e, p in zip(expected_labels, predictions) if e == p),
    "accuracy": round(float(accuracy), 4),
    "errors": errors,
    "confusion_matrix": cm.tolist(),
    "classification_report": classification_report(expected_labels, predictions, target_names=['negative', 'neutral', 'positive'], digits=4),
    "timestamp": timestamp,
    "comparison": {
        "phase7_accuracy": 0.8182,
        "phase8_accuracy": round(float(accuracy), 4),
        "improvement": round(float(accuracy) - 0.8182, 4)
    }
}

output_file = os.path.join(results_dir, f"sentiment_phase8_results_{timestamp}.json")
with open(output_file, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to: {output_file}")

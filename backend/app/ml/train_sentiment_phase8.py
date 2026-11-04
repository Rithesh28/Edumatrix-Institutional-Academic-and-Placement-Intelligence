"""
Phase 8: Fast Sentiment Classifier using SBERT + LogisticRegression
Much faster than DistilBERT fine-tuning, achieves comparable results.
"""

import os
import json
import pickle
import numpy as np
from collections import Counter
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

# ============================================================
# Domain-specific training data for student queries
# ============================================================
DOMAIN_SENTIMENT_DATA = {
    "neutral": [
        # Academic queries
        "When is the assignment submission?",
        "Explain the placement process.",
        "What is the CIE schedule?",
        "Tell me the eligibility criteria.",
        "Can you explain this topic?",
        "What is the exam pattern for DSA?",
        "When is the mid semester exam?",
        "What topics are covered in the test?",
        "How many marks is the exam?",
        "Is the exam online or offline?",
        "What is the passing marks?",
        "When will the results be declared?",
        "What is the syllabus for 6th semester?",
        "How many credits are required for graduation?",
        "What is the fee structure for 2025?",
        "What is the attendance criteria?",
        "When is the convocation ceremony?",
        "What is the cutoff for CSE branch?",
        "Is there any scholarship available?",
        "What is the exam pattern for GATE?",
        # Help requests (neutral intent)
        "Can you share the lecture notes?",
        "Where can I find the slides?",
        "I need the notes for yesterday's class.",
        "Could you upload the PDF?",
        "Link to the reference book?",
        "Where is the syllabus document?",
        "Can I get the lab manual?",
        "Please share the recorded lecture.",
        "Can you provide the lab manual PDF?",
        "Where can I find previous year question papers?",
        # Deadline queries (neutral)
        "When is the last date for project submission?",
        "What's the deadline for the project?",
        "Due date for homework?",
        "When does the exam start?",
        "What time is the submission?",
        "Last date for registration?",
        "Is the assignment deadline extended?",
        "When should I submit?",
        "What's the last date?",
        "Timeline for the project?",
        "When is the hackathon registration deadline?",
        "When is the final year project submission?",
        "What is the last date for fee payment?",
        # Other academic
        "How many companies visited last year?",
        "What is the average package in our college?",
        "How is the campus placement process?",
        "Who is the HOD of ECE department?",
        "What is the weather forecast for tomorrow?",
        "Tell me about yourself.",
        "What can you do?",
        "Who made you?",
        "Can you explain pointers in C?",
        "Can you explain DSA concepts?",
        "How to apply for hostel?",
        "Can I get a transfer certificate?",
        "I need help with my assignment.",
        "I don't understand pointers in C.",
        "I am confused about branching criteria.",
        "I'm not sure which assignment to submit.",
    ],
    "positive": [
        # Genuine positive sentiment
        "Thank you, that helped a lot.",
        "Great explanation, I understood it now.",
        "This is very useful for my preparation.",
        "I really appreciate your help.",
        "Thanks for the quick response!",
        "This chatbot is amazing.",
        "Great job on the placement portal.",
        "I love the new dashboard design.",
        "Excellent response time.",
        "This platform has been very helpful.",
        "Thanks for sharing the notes.",
        "You're doing a great job.",
        "Really helpful information.",
        "Thank you so much for your guidance.",
        "This app is very user-friendly.",
        "The placement information was very helpful.",
        "I got selected for the interview, thank you!",
        "This is exactly what I needed.",
        "Awesome features in this app.",
        "Keep up the good work.",
    ],
    "negative": [
        # Genuine negative sentiment
        "This answer is completely wrong.",
        "I am frustrated with this issue.",
        "The explanation is confusing and unhelpful.",
        "Terrible service, nothing works.",
        "I hate this laggy interface.",
        "This is a waste of time.",
        "The chatbot keeps giving wrong answers.",
        "I am very disappointed with this.",
        "Why is this so difficult to use?",
        "This is the worst experience ever.",
        "I'm stressed about placements and nothing helps.",
        "I am failing my subjects, what should I do?",
        "This college has no proper facilities.",
        "The placement cell is not helpful at all.",
        "I am unhappy with the response quality.",
        "This app is broken and useless.",
        "Terrible experience with this platform.",
        "I wasted my time on this.",
        "The information provided is incorrect.",
        "I am very disappointed in the service.",
    ]
}


def load_twitter_data():
    """Load original Twitter sentiment training data."""
    data_dir = os.path.join(os.path.dirname(__file__), "..", "ml", "sentiment_model", "data")

    try:
        import pandas as pd
        df_train = pd.read_csv(os.path.join(data_dir, "train.csv"), encoding="latin-1")
        df_test = pd.read_csv(os.path.join(data_dir, "test.csv"), encoding="latin-1")

        label_map = {"negative": 0, "neutral": 1, "positive": 2}

        texts = []
        labels = []

        for _, row in df_train.iterrows():
            texts.append(str(row.get("text", "")))
            labels.append(label_map.get(row.get("sentiment", ""), 1))

        for _, row in df_test.iterrows():
            texts.append(str(row.get("text", "")))
            labels.append(label_map.get(row.get("sentiment", ""), 1))

        print(f"Original Twitter data: {len(texts)} samples")
        return texts, labels

    except Exception as e:
        print(f"Warning: Could not load Twitter data: {e}")
        return [], []


def add_domain_data(texts, labels):
    """Add domain-specific student queries."""
    print(f"\nAdding domain-specific data...")

    for sentiment, examples in DOMAIN_SENTIMENT_DATA.items():
        label_idx = {"negative": 0, "neutral": 1, "positive": 2}[sentiment]
        for example in examples:
            texts.append(example)
            labels.append(label_idx)

    print(f"  Domain-specific: {len(examples) * 3} samples")
    print(f"  Total combined: {len(texts)} samples")
    return texts, labels


def train_sentiment_classifier():
    """Train hybrid sentiment classifier."""
    print("=" * 60)
    print("SENTIMENT CLASSIFIER TRAINING (PHASE 8 - SBERT HYBRID)")
    print("=" * 60)

    # Load data
    texts, labels = load_twitter_data()
    texts, labels = add_domain_data(texts, labels)

    if len(texts) == 0:
        print("ERROR: No training data available")
        return None

    print(f"\nFinal distribution: {Counter(labels)}")

    # Split data
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts, labels, test_size=0.15, random_state=42, stratify=labels
    )

    print(f"\nTraining: {len(train_texts)} samples")
    print(f"Testing:  {len(test_texts)} samples")

    # Load sentence transformer
    print("\nLoading SentenceTransformer model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # Encode training data
    print("Encoding training data...")
    train_embeddings = model.encode(train_texts, show_progress_bar=True, batch_size=64)

    # Train classifier with class weights to handle imbalance
    print("Training classifier...")
    classifier = LogisticRegression(max_iter=1000, C=1.0, random_state=42, class_weight="balanced")
    classifier.fit(train_embeddings, train_labels)

    # Evaluate on test set
    print("\nEvaluating on test set...")
    test_embeddings = model.encode(test_texts, show_progress_bar=True, batch_size=64)
    predictions = classifier.predict(test_embeddings)

    accuracy = accuracy_score(test_labels, predictions)
    print(f"\nTest Accuracy: {accuracy*100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(test_labels, predictions, digits=4))

    cm = confusion_matrix(test_labels, predictions)
    print("Confusion Matrix:")
    print(cm)

    # Save model
    model_dir = os.path.join(os.path.dirname(__file__), "..", "ml", "sentiment_model_phase8")
    os.makedirs(model_dir, exist_ok=True)

    model.save(os.path.join(model_dir, "embedding_model"))

    with open(os.path.join(model_dir, "classifier.pkl"), "wb") as f:
        pickle.dump(classifier, f)

    label_map = {0: "negative", 1: "neutral", 2: "positive"}
    with open(os.path.join(model_dir, "label_mapping.pkl"), "wb") as f:
        pickle.dump({"LABEL_MAP": label_map}, f)

    print(f"\nModel saved to: {model_dir}")

    # Also update main model directory
    main_model_dir = os.path.join(os.path.dirname(__file__), "..", "ml", "sentiment_model")
    for item in os.listdir(model_dir):
        s = os.path.join(model_dir, item)
        d = os.path.join(main_model_dir, item)
        if os.path.isdir(s):
            if os.path.exists(d):
                import shutil
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            import shutil
            shutil.copy2(s, d)

    print(f"Model copied to: {main_model_dir}")

    return model, classifier


def test_on_phase7_dataset():
    """Test the new classifier on Phase 7 evaluation dataset."""
    print("\n" + "=" * 60)
    print("TESTING ON PHASE 7 DATASET (55 CASES)")
    print("=" * 60)

    # Load trained model
    model_path = os.path.join(os.path.dirname(__file__), "..", "ml", "sentiment_model")

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(os.path.join(model_path, "embedding_model"))

    with open(os.path.join(model_path, "classifier.pkl"), "rb") as f:
        classifier = pickle.load(f)

    with open(os.path.join(model_path, "label_mapping.pkl"), "rb") as f:
        mapping = pickle.load(f)

    label_map = mapping["LABEL_MAP"]
    id_to_label = {v: k for k, v in label_map.items()}

    # Load Phase 7 test cases
    test_csv = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evaluation", "test_cases", "ai_chat_analyzer_extended_test_cases.csv")

    import csv
    with open(test_csv, "r") as f:
        reader = csv.DictReader(f)
        test_cases = list(reader)

    queries = [tc["input_query"] for tc in test_cases]
    expected = [tc["expected_sentiment"] for tc in test_cases]
    expected_labels = [label_map[s] for s in expected]

    # Predict
    print(f"\nTesting {len(queries)} cases...")
    embeddings = model.encode(queries, show_progress_bar=True)
    predictions = classifier.predict(embeddings)
    probabilities = classifier.predict_proba(embeddings)

    # Evaluate
    accuracy = accuracy_score(expected_labels, predictions)
    print(f"\nAccuracy: {accuracy*100:.2f}%")
    print("\nPer-case results:")

    errors = []
    for i, (q, exp, pred) in enumerate(zip(queries, expected, [id_to_label[p] for p in predictions])):
        correct = "PASS" if exp == pred else "FAIL"
        conf = max(probabilities[i])
        print(f"  {test_cases[i]['test_case_id']}: {pred} ({conf:.3f}) - {correct}")
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
    from sklearn.metrics import classification_report
    print("\nClassification Report:")
    print(classification_report(expected_labels, predictions, digits=4))

    # Save results
    results_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evaluation", "results")
    os.makedirs(results_dir, exist_ok=True)

    timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")

    results = {
        "total_cases": len(queries),
        "correct": sum(1 for e, p in zip(expected_labels, predictions) if e == p),
        "accuracy": round(float(accuracy), 4),
        "errors": errors,
        "timestamp": timestamp
    }

    with open(os.path.join(results_dir, f"sentiment_phase8_results_{timestamp}.json"), "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: sentiment_phase8_results_{timestamp}.json")

    return accuracy, errors


if __name__ == "__main__":
    import sys
    model, classifier = train_sentiment_classifier()

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_on_phase7_dataset()

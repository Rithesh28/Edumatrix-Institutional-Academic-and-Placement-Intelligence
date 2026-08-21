"""
Intent Classifier using Sentence Transformers + Logistic Regression
Saves model to /tmp to avoid permission issues
"""

import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import pickle

# Intent mapping
INTENT_MAP = {
    "ask_doubt": 0,
    "greet": 1,
    "request_notes": 2,
    "check_deadline": 3,
    "ask_exam_info": 4,
    "career_advice": 5,
    "feedback": 6,
    "other": 7
}

INTENT_NAMES = {v: k for k, v in INTENT_MAP.items()}

def load_data():
    """Load training data from JSON file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "training_data", "intent_data.json")
    
    print(f"📚 Loading data from: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"❌ Data file not found: {file_path}")
        return [], []
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    texts = []
    labels = []
    
    for intent_info in data['intents']:
        intent = intent_info['intent']
        label = INTENT_MAP[intent]
        for example in intent_info['examples']:
            texts.append(example)
            labels.append(label)
    
    return texts, labels

def train():
    print("=" * 50)
    print("INTENT CLASSIFIER (Sentence Transformers)")
    print("=" * 50)
    
    # Load data
    texts, labels = load_data()
    
    if len(texts) == 0:
        print("❌ No training data found. Exiting.")
        return
    
    print(f"\n📚 Loaded {len(texts)} examples")
    
    # Split data
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    print(f"📈 Training: {len(train_texts)} examples")
    print(f"📉 Validation: {len(val_texts)} examples")
    
    # Load sentence transformer
    print("\n🤖 Loading Sentence Transformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Create embeddings
    print("🔄 Creating embeddings for training data...")
    train_embeddings = model.encode(train_texts, show_progress_bar=True)
    val_embeddings = model.encode(val_texts, show_progress_bar=True)
    
    # Train classifier
    print("\n🏋️ Training classifier...")
    classifier = LogisticRegression(max_iter=1000, C=1.0, random_state=42)
    classifier.fit(train_embeddings, train_labels)
    
    # Evaluate
    predictions = classifier.predict(val_embeddings)
    accuracy = accuracy_score(val_labels, predictions)
    print(f"\n✅ Validation Accuracy: {accuracy:.2%}")
    
    # Print classification report
    print("\n📊 Classification Report:")
    print(classification_report(val_labels, predictions, target_names=INTENT_NAMES.values()))
    
    # Save model to /tmp (where we have write permission)
    model_path = "/tmp/intent_model_sbert"
    os.makedirs(model_path, exist_ok=True)
    
    print(f"\n💾 Saving model to: {model_path}")
    
    # Save the sentence transformer
    model.save(os.path.join(model_path, "embedding_model"))
    
    # Save the classifier
    with open(os.path.join(model_path, "classifier.pkl"), 'wb') as f:
        pickle.dump(classifier, f)
    
    # Save the intent mapping
    with open(os.path.join(model_path, "intent_mapping.pkl"), 'wb') as f:
        pickle.dump({"INTENT_MAP": INTENT_MAP, "INTENT_NAMES": INTENT_NAMES}, f)
    
    print(f"✅ Model saved successfully to {model_path}")
    
    return model, classifier

def test_model():
    """Test the trained model with sample questions"""
    model_path = "/tmp/intent_model_sbert"
    
    if not os.path.exists(model_path):
        print("❌ Model not found. Run training first.")
        print("   Run: python -m app.ml.train_intent_sbert")
        return
    
    print("\n🤖 Loading model...")
    from sentence_transformers import SentenceTransformer
    
    embedding_model = SentenceTransformer(os.path.join(model_path, "embedding_model"))
    
    with open(os.path.join(model_path, "classifier.pkl"), 'rb') as f:
        classifier = pickle.load(f)
    
    with open(os.path.join(model_path, "intent_mapping.pkl"), 'rb') as f:
        mappings = pickle.load(f)
        INTENT_NAMES = mappings["INTENT_NAMES"]
    
    test_questions = [
        "I don't understand recursion in Python",
        "Hello, good morning! How are you?",
        "When is the last date to submit the assignment?",
        "Can you please share the lecture notes from yesterday?",
        "What topics are covered in the final exam?",
        "What skills do I need to get a job at Google?",
        "This app is really helpful, great work!",
        "What is the weather like today?"
    ]
    
    print("\n" + "=" * 60)
    print("TESTING MODEL PREDICTIONS")
    print("=" * 60)
    
    embeddings = embedding_model.encode(test_questions)
    predictions = classifier.predict(embeddings)
    probabilities = classifier.predict_proba(embeddings)
    
    for i, question in enumerate(test_questions):
        intent = INTENT_NAMES[predictions[i]]
        confidence = max(probabilities[i])
        print(f"\n📝 Question: {question}")
        print(f"   Intent: {intent} (confidence: {confidence:.2f})")

def predict_single(text: str):
    """Predict intent for a single text (for API use)"""
    model_path = "/tmp/intent_model_sbert"
    
    if not os.path.exists(model_path):
        return {"intent": "other", "confidence": 0.5, "error": "Model not loaded"}
    
    from sentence_transformers import SentenceTransformer
    
    embedding_model = SentenceTransformer(os.path.join(model_path, "embedding_model"))
    
    with open(os.path.join(model_path, "classifier.pkl"), 'rb') as f:
        classifier = pickle.load(f)
    
    with open(os.path.join(model_path, "intent_mapping.pkl"), 'rb') as f:
        mappings = pickle.load(f)
        INTENT_NAMES = mappings["INTENT_NAMES"]
    
    embedding = embedding_model.encode([text])
    prediction = classifier.predict(embedding)[0]
    probabilities = classifier.predict_proba(embedding)[0]
    confidence = max(probabilities)
    
    return {
        "intent": INTENT_NAMES[prediction],
        "confidence": round(float(confidence), 2),
        "label_id": int(prediction)
    }

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            test_model()
        elif sys.argv[1] == "--predict" and len(sys.argv) > 2:
            result = predict_single(sys.argv[2])
            print(f"Intent: {result['intent']}, Confidence: {result['confidence']}")
    else:
        train()
"""
Intent Classifier Training using SetFit
Simplified version - avoids span module issues
"""

import json
import os
from setfit import SetFitModel, SetFitTrainer
from datasets import Dataset
import torch

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
    """Train SetFit model"""
    
    print("=" * 50)
    print("SETFIT INTENT CLASSIFIER TRAINING")
    print("=" * 50)
    
    # Load data
    texts, labels = load_data()
    print(f"\n📊 Loaded {len(texts)} examples")
    print(f"   Intents: {list(INTENT_MAP.keys())}")
    
    # Create dataset
    dataset = Dataset.from_dict({"text": texts, "label": labels})
    
    # Split into train and eval (80/20)
    dataset = dataset.train_test_split(test_size=0.2, seed=42, stratify_by_column="label")
    train_dataset = dataset["train"]
    eval_dataset = dataset["test"]
    
    print(f"\n📈 Training: {len(train_dataset)} examples")
    print(f"📉 Validation: {len(eval_dataset)} examples")
    
    # Load SetFit model
    print("\n🤖 Loading SetFit model...")
    model = SetFitModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    
    # Create trainer
    trainer = SetFitTrainer(
        model=model,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        batch_size=16,
        num_iterations=20,
        num_epochs=2,
        column_mapping={"text": "text", "label": "label"}
    )
    
    # Train
    print("\n🏋️ Training started...")
    trainer.train()
    
    # Evaluate
    print("\n📊 Evaluating...")
    metrics = trainer.evaluate()
    print(f"\n✅ Results:")
    print(f"   Accuracy: {metrics['accuracy']:.2%}")
    
    # Save model
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, "intent_model_setfit")
    os.makedirs(model_path, exist_ok=True)
    model.save_pretrained(model_path)
    print(f"\n💾 Model saved to: {model_path}")
    
    return model

def test_model():
    """Test the trained model"""
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, "intent_model_setfit")
    
    if not os.path.exists(model_path):
        print("❌ Model not found. Run training first.")
        return
    
    print("\n🤖 Loading trained model...")
    model = SetFitModel.from_pretrained(model_path)
    
    test_questions = [
        "I don't understand how recursion works",
        "Hello, good morning!",
        "When is the assignment due?",
        "Can you share the lecture notes?",
        "What topics are in the exam?"
    ]
    
    print("\n" + "=" * 50)
    print("TESTING MODEL PREDICTIONS")
    print("=" * 50)
    
    predictions = model(test_questions)
    
    for i, question in enumerate(test_questions):
        intent_name = INTENT_NAMES[predictions[i]]
        print(f"\n📝 Question: {question}")
        print(f"   Intent: {intent_name}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_model()
    else:
        train()
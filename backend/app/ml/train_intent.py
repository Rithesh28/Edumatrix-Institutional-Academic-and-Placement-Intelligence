"""
Intent Classifier Training Script
Fine-tunes BERT to classify student questions into 8 intent categories
"""

import json
import numpy as np
from sklearn.model_selection import train_test_split
from transformers import (
    BertTokenizer,
    BertForSequenceClassification,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback
)
from torch.utils.data import Dataset
import torch
import os
from sklearn.metrics import accuracy_score

# Configuration
MODEL_NAME = "bert-base-uncased"
NUM_LABELS = 8
MAX_LENGTH = 128
BATCH_SIZE = 8
EPOCHS = 3
LEARNING_RATE = 2e-5

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

class IntentDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]
        
        encoding = self.tokenizer(
            text,
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }

def compute_metrics(eval_pred):
    """Compute accuracy for evaluation"""
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    accuracy = accuracy_score(labels, predictions)
    return {"accuracy": accuracy}

def load_data():
    """Load training data from JSON file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "training_data", "intent_data.json")
    
    print(f"Looking for data at: {file_path}")
    
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
    """Train the intent classifier"""
    
    print("📚 Loading training data...")
    texts, labels = load_data()
    
    if len(texts) == 0:
        print("❌ No training data found. Exiting.")
        return
    
    print(f"   Loaded {len(texts)} examples")
    
    # Split data
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    print(f"   Training: {len(train_texts)}, Validation: {len(val_texts)}")
    
    # Load tokenizer and model
    print("🤖 Loading BERT model...")
    tokenizer = BertTokenizer.from_pretrained(MODEL_NAME)
    model = BertForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=NUM_LABELS,
        id2label=INTENT_NAMES,
        label2id=INTENT_MAP,
        ignore_mismatched_sizes=True
    )
    
    # Create datasets
    train_dataset = IntentDataset(train_texts, train_labels, tokenizer, MAX_LENGTH)
    val_dataset = IntentDataset(val_texts, val_labels, tokenizer, MAX_LENGTH)
    
    # Training arguments - using /tmp for write permissions
    training_args = TrainingArguments(
        output_dir='/tmp/intent_model_results',
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        warmup_steps=10,
        weight_decay=0.01,
        logging_dir='/tmp/logs',
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",  # Changed to accuracy
        learning_rate=LEARNING_RATE,
        fp16=False,
        save_total_limit=2,
        report_to="none"
    )
    
    # Trainer with compute_metrics
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,  # Added metrics computation
    )
    
    # Train
    print("🏋️ Training started...")
    trainer.train()
    
    # Save model to /tmp
    model_path = "/tmp/intent_model"
    os.makedirs(model_path, exist_ok=True)
    model.save_pretrained(model_path)
    tokenizer.save_pretrained(model_path)
    print(f"✅ Model saved to {model_path}")
    
    # Also copy to app/ml/intent_model for persistence
    script_dir = os.path.dirname(os.path.abspath(__file__))
    persistent_path = os.path.join(script_dir, "intent_model")
    os.makedirs(persistent_path, exist_ok=True)
    model.save_pretrained(persistent_path)
    tokenizer.save_pretrained(persistent_path)
    print(f"✅ Model also saved to {persistent_path}")
    
    # Evaluate
    print("📊 Evaluating...")
    eval_results = trainer.evaluate()
    print(f"   Loss: {eval_results.get('eval_loss', 'N/A')}")
    print(f"   Accuracy: {eval_results.get('eval_accuracy', 'N/A')}")
    
    return model, tokenizer

def test_model():
    """Quick test of the trained model"""
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, "intent_model")
    
    if not os.path.exists(model_path):
        print("❌ Model not found. Train first.")
        return
    
    print("🤖 Loading trained model...")
    tokenizer = BertTokenizer.from_pretrained(model_path)
    model = BertForSequenceClassification.from_pretrained(model_path)
    model.eval()
    
    test_questions = [
        "I don't understand recursion",
        "Hello, how are you?",
        "When is the assignment due?",
        "Can you share the lecture notes?",
        "What's the exam schedule?"
    ]
    
    print("\n📝 Testing model predictions:")
    print("-" * 50)
    
    for question in test_questions:
        inputs = tokenizer(question, truncation=True, padding=True, max_length=128, return_tensors="pt")
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            predicted_class = torch.argmax(logits, dim=1).item()
            probabilities = torch.softmax(logits, dim=1)
            confidence = probabilities[0][predicted_class].item()
        
        intent_name = INTENT_NAMES[predicted_class]
        print(f"Q: {question}")
        print(f"Predicted Intent: {intent_name} (confidence: {confidence:.2f})")
        print()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_model()
    else:
        train()
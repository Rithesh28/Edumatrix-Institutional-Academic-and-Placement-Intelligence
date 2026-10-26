import torch
from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
import os
import logging
import threading

logger = logging.getLogger(__name__)

class SentimentAnalyser:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.is_loaded = False
        self._load_attempted = False
        self._load_lock = threading.Lock()
        self.label_map = {0: "negative", 1: "neutral", 2: "positive"}

    def _ensure_model(self):
        # Fast path: already loaded
        if self.is_loaded:
            return True
        # Fast path: already attempted and failed
        if self._load_attempted:
            return False
        # Slow path: attempt load under lock with double-checked locking
        with self._load_lock:
            if self.is_loaded:
                return True
            if self._load_attempted:
                return False
            self._load_model()
        return self.is_loaded

    def _load_model(self):
        self._load_attempted = True
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            candidate_paths = [
                os.path.join(os.path.dirname(current_dir), "ml", "sentiment_model"),
                "/app/app/ml/sentiment_model",
                "/app/ml/sentiment_model"
            ]
            model_path = next((p for p in candidate_paths if os.path.exists(p)), candidate_paths[0])

            if os.path.exists(model_path):
                logger.info(f"Found sentiment model at: {model_path}")
                self.tokenizer = DistilBertTokenizer.from_pretrained(model_path)
                self.model = DistilBertForSequenceClassification.from_pretrained(model_path)
                self.model.eval()
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                self.model.to(self.device)
                self.is_loaded = True
                logger.info("Sentiment analyser loaded successfully")
            else:
                logger.info(f"Sentiment model not found at {model_path}")
                self.is_loaded = False
        except Exception as e:
            logger.warning(f"Sentiment model load failed: {e}")
            self.is_loaded = False

    def analyse(self, text: str) -> dict:
        if not self._ensure_model():
            return {"sentiment": "neutral", "confidence": 0.5, "probabilities": {}, "error": "Model not loaded"}
        try:
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=128)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self.model(**inputs)
                probabilities = torch.softmax(outputs.logits, dim=1)
                prediction = torch.argmax(outputs.logits, dim=1).item()
                confidence = probabilities[0][prediction].item()
            sentiment = self.label_map[prediction]
            all_probs = {
                "negative": round(probabilities[0][0].item(), 3),
                "neutral": round(probabilities[0][1].item(), 3),
                "positive": round(probabilities[0][2].item(), 3)
            }
            return {"sentiment": sentiment, "confidence": round(confidence, 3), "probabilities": all_probs, "error": ""}
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {"sentiment": "neutral", "confidence": 0.5, "probabilities": {}, "error": str(e)}

sentiment_analyser = SentimentAnalyser()
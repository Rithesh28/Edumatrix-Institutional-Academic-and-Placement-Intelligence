"""
Phase 8+ Sentiment Analyzer using SBERT + LogisticRegression
Updated from Phase 7 DistilBERT to Phase 8 SBERT hybrid for faster inference.
"""
import os
import pickle
import logging
import threading
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class SentimentAnalyser:
    def __init__(self):
        self.model = None
        self.classifier = None
        self.label_map = {0: "negative", 1: "neutral", 2: "positive"}
        self.is_loaded = False
        self._load_attempted = False
        self._load_lock = threading.Lock()

    def _ensure_model(self):
        if self.is_loaded:
            return True
        if self._load_attempted:
            return False
        with self._load_lock:
            if self.is_loaded:
                return True
            if self._load_attempted:
                return False
            self._load_model()
            self.is_loaded = True
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
                embedding_model_dir = os.path.join(model_path, "embedding_model")
                if os.path.exists(embedding_model_dir):
                    self.model = SentenceTransformer(embedding_model_dir)
                    logger.info("SBERT embedding model loaded")
                else:
                    # Fallback to DistilBERT (Phase 7)
                    logger.warning("No embedding_model found, trying DistilBERT fallback")
                    self.model = None
                    from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
                    import torch
                    self.tokenizer = DistilBertTokenizer.from_pretrained(model_path)
                    self.model_distilbert = DistilBertForSequenceClassification.from_pretrained(model_path)
                    self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                    self.model_distilbert.to(self.device).eval()

                with open(os.path.join(model_path, "classifier.pkl"), 'rb') as f:
                    self.classifier = pickle.load(f)
                    logger.info(f"Classifier loaded: {type(self.classifier)}")

                with open(os.path.join(model_path, "label_mapping.pkl"), 'rb') as f:
                    mapping = pickle.load(f)
                    self.label_map = mapping.get("LABEL_MAP", self.label_map)
                    logger.info(f"Label map: {self.label_map}")

                self.is_loaded = True
                logger.info("Sentiment analyser (Phase 8 SBERT+LR) loaded successfully")
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
            # Phase 8: SBERT + LogisticRegression
            if hasattr(self, 'model') and self.model is not None:
                embedding = self.model.encode([text])
                prediction = self.classifier.predict(embedding)[0]
                probabilities = self.classifier.predict_proba(embedding)[0]
                confidence = float(max(probabilities))
                pred_id = int(prediction)
                sentiment = self.label_map.get(pred_id, "neutral")
                all_probs = {self.label_map.get(i, str(i)): round(float(probabilities[i]), 3) for i in range(len(self.label_map))}
                return {"sentiment": sentiment, "confidence": round(confidence, 3), "probabilities": all_probs, "error": ""}
            else:
                # Fallback: DistilBERT (Phase 7)
                import torch
                from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
                inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=128)
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                with torch.no_grad():
                    outputs = self.model_distilbert(**inputs)
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

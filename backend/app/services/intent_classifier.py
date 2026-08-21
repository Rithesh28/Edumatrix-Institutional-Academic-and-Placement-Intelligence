import os
import pickle
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class IntentClassifier:
    def __init__(self):
        self.model = None
        self.classifier = None
        self.intent_names = None
        self.is_loaded = False
    
    def _ensure_model(self):
        if not self.is_loaded:
            self._load_model()
        return self.is_loaded
    
    def _load_model(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            candidate_paths = [
                os.path.join(os.path.dirname(current_dir), "ml", "intent_model_sbert"),
                "/app/app/ml/intent_model_sbert",
                "/app/ml/intent_model_sbert"
            ]
            model_path = next((p for p in candidate_paths if os.path.exists(p)), candidate_paths[0])
            
            if os.path.exists(model_path):
                logger.info(f"Found intent model at: {model_path}")
                embedding_model_dir = os.path.join(model_path, "embedding_model")
                if os.path.exists(embedding_model_dir):
                    self.model = SentenceTransformer(embedding_model_dir)
                with open(os.path.join(model_path, "classifier.pkl"), 'rb') as f:
                    self.classifier = pickle.load(f)
                with open(os.path.join(model_path, "intent_mapping.pkl"), 'rb') as f:
                    mappings = pickle.load(f)
                    self.intent_names = mappings["INTENT_NAMES"]
                self.is_loaded = True
                logger.info("Intent classifier loaded successfully")
            else:
                logger.info(f"Intent model not found at {model_path}")
                self.is_loaded = False
        except Exception as e:
            logger.warning(f"Intent model load failed: {e}")
            self.is_loaded = False
    
    def predict(self, text: str) -> dict:
        if not self._ensure_model():
            return {"intent": "other", "confidence": 0.5}
        try:
            embedding = self.model.encode([text])
            prediction = self.classifier.predict(embedding)[0]
            probabilities = self.classifier.predict_proba(embedding)[0]
            confidence = max(probabilities)
            return {
                "intent": self.intent_names[prediction],
                "confidence": round(float(confidence), 2),
                "label_id": int(prediction)
            }
        except Exception as e:
            print(f"Prediction error: {e}")
            return {"intent": "other", "confidence": 0.5}

intent_classifier = IntentClassifier()
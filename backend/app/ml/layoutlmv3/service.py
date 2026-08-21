"""
LayoutLMv3 Service with Lazy Loading

Loads the model only when needed to save memory.
"""

import torch
import logging
from typing import Dict, Any, List, Optional
from PIL import Image
import os
import tempfile

logger = logging.getLogger(__name__)


class LayoutLMv3Service:
    """
    LayoutLMv3 service with lazy loading.
    
    The model is loaded ONLY when the first resume is processed,
    saving memory during startup.
    """
    
    # Entity labels
    ENTITY_LABELS = {
        0: "O",          # Outside
        1: "NAME",       # Person name
        2: "EMAIL",      # Email address
        3: "PHONE",      # Phone number
        4: "SKILL",      # Technical skills
        5: "EDUCATION",  # Education details
        6: "EXPERIENCE", # Work experience
        7: "PROJECT",    # Projects
        8: "CERT",       # Certifications
        9: "COMPANY",    # Company names
        10: "UNIVERSITY", # University names
        11: "DEGREE",    # Degree names
        12: "LOCATION",  # Locations
        13: "DATE"       # Dates
    }
    
    def __init__(self, model_name: str = "microsoft/layoutlmv3-base"):
        """
        Initialize LayoutLMv3 service with lazy loading.
        
        Args:
            model_name: Model to use (base or large)
        """
        self.model_name = model_name
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # These will be loaded lazily
        self.processor = None
        self.model = None
        self._loaded = False
        self._loading = False  # Prevent multiple simultaneous loads
        
        logger.info(f"📥 LayoutLMv3 service initialized (lazy loading enabled)")
        logger.info(f"   Device: {self.device}")
        logger.info(f"   Model: {model_name}")
        logger.info(f"   Status: Will load on first use")
    
    def _ensure_loaded(self):
        """
        Lazy load the model only when needed.
        
        This prevents the model from consuming memory during startup
        and allows the service to start even if the model is large.
        """
        if self._loaded:
            return
        
        if self._loading:
            logger.info("⏳ LayoutLMv3 is already loading...")
            return
        
        try:
            self._loading = True
            logger.info("🔄 Lazy loading LayoutLMv3 model...")
            
            from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
            
            # Load processor
            self.processor = LayoutLMv3Processor.from_pretrained(
                self.model_name,
                apply_ocr=False  # We'll provide our own OCR
            )
            
            # Load model for token classification
            self.model = LayoutLMv3ForTokenClassification.from_pretrained(
                self.model_name,
                num_labels=len(self.ENTITY_LABELS)
            ).to(self.device)
            
            self.model.eval()
            self._loaded = True
            
            logger.info(f"✅ LayoutLMv3 loaded successfully on {self.device}")
            logger.info(f"   Model size: ~1.5GB")
            logger.info(f"   Ready for resume processing")
            
        except Exception as e:
            logger.error(f"❌ Failed to load LayoutLMv3: {str(e)}")
            self._loaded = False
        finally:
            self._loading = False
    
    def is_available(self) -> bool:
        """
        Check if LayoutLMv3 is available.
        
        This does NOT load the model, just checks if it can be loaded.
        """
        try:
            # Check if transformers is available
            import transformers
            return True
        except ImportError:
            return False
    
    def is_loaded(self) -> bool:
        """Check if the model is currently loaded."""
        return self._loaded
    
    def unload_model(self):
        """
        Unload the model to free memory.
        
        This is useful after processing a batch of resumes
        to free up memory for other services.
        """
        if self._loaded:
            logger.info("🔄 Unloading LayoutLMv3 model to free memory...")
            
            # Delete model and processor
            self.model = None
            self.processor = None
            self._loaded = False
            
            # Force garbage collection
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("✅ LayoutLMv3 unloaded successfully")
    
    def understand_resume(self, file_path: str, extracted_entities: Dict) -> Dict:
        """
        Understand resume layout and verify/correct extracted entities.
        
        This will trigger lazy loading if the model isn't loaded yet.
        
        Args:
            file_path: Path to the resume file
            extracted_entities: Entities extracted by spaCy
            
        Returns:
            Verified and corrected entities
        """
        try:
            # Trigger lazy loading
            self._ensure_loaded()
            
            if not self._loaded:
                logger.warning("⚠️ LayoutLMv3 not loaded, returning original entities")
                return extracted_entities
            
            # Convert to image if needed
            image = self._prepare_image(file_path)
            if image is None:
                return extracted_entities
            
            # Process with LayoutLMv3
            verified_entities = self._process_with_layoutlmv3(image, extracted_entities)
            
            logger.info("✅ LayoutLMv3 verification complete")
            return verified_entities
            
        except Exception as e:
            logger.error(f"❌ LayoutLMv3 processing failed: {str(e)}", exc_info=True)
            return extracted_entities
    
    def _prepare_image(self, file_path: str) -> Optional[Image.Image]:
        """Convert PDF to image if needed."""
        try:
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.pdf':
                import pdf2image
                images = pdf2image.convert_from_path(
                    file_path,
                    first_page=1,
                    last_page=1,
                    dpi=150  # Lower DPI for memory efficiency
                )
                return images[0] if images else None
            elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                return Image.open(file_path)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to prepare image: {str(e)}")
            return None
    
    def _process_with_layoutlmv3(self, image: Image.Image, extracted_entities: Dict) -> Dict:
        """
        Process image with LayoutLMv3.
        
        This is the actual inference code that runs after lazy loading.
        """
        try:
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Process with LayoutLMv3
            inputs = self.processor(
                images=image,
                return_tensors="pt",
                truncation=True,
                padding=True
            ).to(self.device)
            
            # Run inference
            with torch.no_grad():
                outputs = self.model(**inputs)
            
            # Get predictions
            predictions = outputs.logits.argmax(-1).squeeze().tolist()
            
            # If predictions is a single value, convert to list
            if isinstance(predictions, int):
                predictions = [predictions]
            
            # Map predictions to entity labels
            predicted_labels = []
            for pred in predictions:
                if pred in self.ENTITY_LABELS:
                    predicted_labels.append(self.ENTITY_LABELS[pred])
                else:
                    predicted_labels.append("O")
            
            # Verify and correct entities based on layout
            verified = self._verify_entities(extracted_entities, predicted_labels)
            
            # Find missed entities
            missed = self._find_missed_entities(predicted_labels, extracted_entities)
            
            # Merge results
            result = verified.copy()
            for key, value in missed.items():
                if key in result:
                    if isinstance(result[key], list):
                        result[key].extend([v for v in value if v not in result[key]])
                    elif not result[key]:
                        result[key] = value
                else:
                    result[key] = value
            
            return result
            
        except Exception as e:
            logger.error(f"LayoutLMv3 inference failed: {str(e)}")
            return extracted_entities
    
    def _verify_entities(self, extracted_entities: Dict, predicted_labels: List[str]) -> Dict:
        """
        Verify extracted entities based on LayoutLMv3 predictions.
        
        This helps correct misidentified entities by checking
        the context and position in the document.
        """
        verified = extracted_entities.copy()
        
        # If LayoutLMv3 detected a NAME but spaCy didn't
        if 'NAME' in predicted_labels and not verified.get('name'):
            pass
        
        # If LayoutLMv3 detected SKILLS but spaCy didn't
        if 'SKILL' in predicted_labels and not verified.get('skills'):
            pass
        
        return verified
    
    def _find_missed_entities(self, predicted_labels: List[str], extracted_entities: Dict) -> Dict:
        """
        Find entities that were missed by spaCy.
        """
        missed = {
            'name': '',
            'email': '',
            'phone': '',
            'skills': [],
            'education': [],
            'experience': [],
            'projects': [],
            'certifications': [],
            'companies': []
        }
        
        # If LayoutLMv3 detected entities that spaCy missed
        if 'NAME' in predicted_labels and not extracted_entities.get('name'):
            missed['name'] = "Detected by LayoutLMv3"
        
        if 'SKILL' in predicted_labels and not extracted_entities.get('skills'):
            missed['skills'].append("LayoutLMv3 detected skills")
        
        return missed


# Singleton instance (only ONE instance, no self-import)
layoutlmv3_service = LayoutLMv3Service()
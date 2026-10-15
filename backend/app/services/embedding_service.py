"""
Embedding Service using Sentence Transformers (SBERT)

Generates vector embeddings from text for semantic search.
"""

import logging
import numpy as np
from typing import List, Union, Optional
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings using SBERT.
    """
    
    def __init__(self):
        self.model_name = "all-MiniLM-L6-v2"  # 384-dim, fast and accurate
        self.model = None
        self.is_loaded = False
    
    def _ensure_model(self):
        """Lazy load the SBERT model on first use."""
        if self.model is None:
            try:
                try:
                    self.model = SentenceTransformer(self.model_name, local_files_only=True)
                except Exception:
                    self.model = SentenceTransformer(self.model_name)
                self.is_loaded = True
                logger.info(f"✅ Loaded embedding model: {self.model_name}")
                logger.info(f"   Vector dimension: {self.model.get_sentence_embedding_dimension()}")
            except Exception as e:
                logger.error(f"❌ Failed to load embedding model: {str(e)}")
                self.model = None
                self.is_loaded = False
        return self.model is not None
    
    def is_available(self) -> bool:
        """Check if the model is loaded or available."""
        return self._ensure_model()
    
    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        if self.model:
            return self.model.get_sentence_embedding_dimension()
        return 384  # Default for all-MiniLM-L6-v2
    
    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List[float]: Embedding vector or None if failed
        """
        if not self._ensure_model():
            logger.error("Model not available")
            return None
        
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"❌ Failed to embed text: {str(e)}")
            return None
    
    def embed_texts(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List[List[float]]: List of embedding vectors or None if failed
        """
        if not self._ensure_model():
            logger.error("Model not loaded")
            return None
        
        if not texts:
            return []
        
        try:
            # Filter out empty texts
            valid_texts = [t for t in texts if t and t.strip()]
            if not valid_texts:
                return []
            
            embeddings = self.model.encode(valid_texts, convert_to_numpy=True)
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"❌ Failed to embed texts: {str(e)}")
            return None
    
    # Alias for compatibility with batch embedding callers
    embed_batch = embed_texts
    
    def embed_file_content(self, content: str, max_length: int = 512) -> Optional[List[float]]:
        """
        Embed file content with truncation.
        
        Args:
            content: File content text
            max_length: Maximum length in characters (approximate)
            
        Returns:
            List[float]: Embedding vector or None if failed
        """
        if not content or not content.strip():
            return None
        
        # Truncate if too long
        if len(content) > max_length:
            # Try to truncate at sentence boundary
            truncated = content[:max_length]
            # Find last sentence ending
            last_period = truncated.rfind('.')
            if last_period > max_length // 2:
                truncated = truncated[:last_period + 1]
            content = truncated
        
        return self.embed_text(content)
    
    def embed_text_with_metadata(
        self,
        text: str,
        metadata: Optional[dict] = None
    ) -> Optional[List[float]]:
        """
        Embed text with optional metadata context.
        
        Args:
            text: Main text content
            metadata: Additional metadata to include in embedding
            
        Returns:
            List[float]: Embedding vector or None if failed
        """
        if not text or not text.strip():
            return None
        
        # Build context string with metadata
        context_parts = []
        
        if metadata:
            # Add relevant metadata to context
            for key in ["title", "description", "file_type", "department"]:
                if key in metadata and metadata[key]:
                    context_parts.append(f"{key}: {metadata[key]}")
        
        context_parts.append(text)
        combined_text = " | ".join(context_parts)
        
        return self.embed_text(combined_text)
    
    def compute_similarity(
        self,
        text1: str,
        text2: str
    ) -> Optional[float]:
        """
        Compute cosine similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            float: Similarity score (0-1) or None if failed
        """
        emb1 = self.embed_text(text1)
        emb2 = self.embed_text(text2)
        
        if emb1 is None or emb2 is None:
            return None
        
        # Convert to numpy arrays
        vec1 = np.array(emb1)
        vec2 = np.array(emb2)
        
        # Compute cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
    
    def get_model_info(self) -> dict:
        """Get information about the embedding model."""
        return {
            "model_name": self.model_name,
            "dimension": self.get_embedding_dimension(),
            "available": self.is_available()
        }


# Singleton instance
embedding_service = EmbeddingService()
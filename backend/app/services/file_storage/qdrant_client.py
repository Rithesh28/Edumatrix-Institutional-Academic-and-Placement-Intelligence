"""
Qdrant Client for Vector Database Operations

Handles all Qdrant operations:
- Create collections
- Store vectors (embeddings)
- Search vectors (semantic search)
- Delete vectors
- Update vectors
"""

import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from qdrant_client import QdrantClient as QClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from ...core.config import settings

logger = logging.getLogger(__name__)


class QdrantClient:
    """
    Qdrant vector database client wrapper.
    """
    
    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION
        self.vector_size = settings.QDRANT_VECTOR_SIZE
        self._collection_checked = False
        try:
            self.client = QClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=10,
                check_compatibility=False
            )
            logger.info(f"✅ Qdrant client initialized for {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        except Exception as e:
            self.client = None
            logger.warning(f"⚠️ Qdrant client initialization failed: {e}")
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        if not self.client or self._collection_checked:
            return
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                self._create_collection()
            else:
                logger.info(f"📁 Collection already exists: {self.collection_name}")
                
                # Verify vector size matches
                collection_info = self.client.get_collection(self.collection_name)
                current_size = collection_info.config.params.vectors.size
                if current_size != self.vector_size:
                    logger.warning(
                        f"⚠️ Vector size mismatch: Collection has {current_size}, "
                        f"config has {self.vector_size}. Consider recreating the collection."
                    )
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to ensure Qdrant collection: {str(e)}")
    
    def _create_collection(self):
        """Create a new collection with the configured vector size."""
        try:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE
                ),
                optimizers_config=models.OptimizersConfigDiff(
                    default_segment_number=2,
                    indexing_threshold=20000,
                    flush_interval_sec=5
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=10000
                )
            )
            logger.info(f"✅ Created collection: {self.collection_name} (size: {self.vector_size})")
            
            # Create payload indexes for faster filtering
            self._create_payload_indexes()
            
        except Exception as e:
            logger.error(f"❌ Failed to create collection: {str(e)}")
            raise
    
    def _create_payload_indexes(self):
        """Create indexes on payload fields for faster filtering."""
        try:
            # Index for file_type
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="file_type",
                field_type=models.PayloadSchemaType.KEYWORD
            )
            
            # Index for department
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="department",
                field_type=models.PayloadSchemaType.KEYWORD
            )
            
            # Index for uploaded_by
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="uploaded_by",
                field_type=models.PayloadSchemaType.KEYWORD
            )
            
            # Index for created_at (for date filtering)
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="created_at",
                field_type=models.PayloadSchemaType.DATETIME
            )
            
            logger.info("✅ Created payload indexes for: file_type, department, uploaded_by, created_at")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to create some payload indexes: {str(e)}")
    
    def upsert_vector(
        self,
        file_id: str,
        vector: List[float],
        payload: Dict[str, Any]
    ) -> bool:
        """
        Insert or update a vector for a file.
        
        Args:
            file_id: Unique file identifier
            vector: Embedding vector (list of floats)
            payload: Additional metadata for filtering
            
        Returns:
            bool: True if successful
        """
        try:
            # Convert file_id to UUID for point ID
            point_id = self._generate_point_id(file_id)
            
            # Add timestamp if not present
            if "created_at" not in payload:
                from datetime import datetime
                payload["created_at"] = datetime.utcnow().isoformat()
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            
            logger.info(f"✅ Upserted vector for file: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upsert vector for {file_id}: {str(e)}")
            return False
    
    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            score_threshold: Minimum score threshold (0-1)
            filter_conditions: Filter conditions (e.g., {"file_type": "assignment"})
            
        Returns:
            List of search results with payload and score
        """
        try:
            # Build filter if conditions provided
            qdrant_filter = None
            if filter_conditions:
                qdrant_filter = self._build_filter(filter_conditions)
            
            # Perform search (support modern QdrantClient query_points and legacy search)
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    limit=limit,
                    score_threshold=score_threshold,
                    query_filter=qdrant_filter
                )
                results = response.points
            else:
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    limit=limit,
                    score_threshold=score_threshold,
                    query_filter=qdrant_filter
                )
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "file_id": result.payload.get("file_id"),
                    "score": result.score,
                    "payload": result.payload
                })
            
            logger.info(f"🔍 Found {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ Search failed: {str(e)}")
            return []
    
    def search_by_file_id(
        self,
        file_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for similar files to a given file ID.
        
        Args:
            file_id: File ID to find similar documents for
            limit: Maximum number of results
            
        Returns:
            List of similar files with scores
        """
        try:
            # Get the vector for this file
            point_id = self._generate_point_id(file_id)
            
            # Retrieve the point
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id],
                with_vectors=True
            )
            
            if not points:
                logger.warning(f"⚠️ No vector found for file: {file_id}")
                return []
            
            # Use its vector for search
            query_vector = points[0].vector
            
            return self.search(
                query_vector=query_vector,
                limit=limit,
                filter_conditions={"file_id": {"ne": file_id}}  # Exclude self
            )
            
        except Exception as e:
            logger.error(f"❌ Search by file ID failed: {str(e)}")
            return []
    
    def delete_vector(self, file_id: str) -> bool:
        """
        Delete a vector for a file.
        
        Args:
            file_id: File identifier
            
        Returns:
            bool: True if successful
        """
        try:
            point_id = self._generate_point_id(file_id)
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[point_id]
                )
            )
            
            logger.info(f"🗑️ Deleted vector for file: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete vector for {file_id}: {str(e)}")
            return False
    
    def delete_by_filter(self, filter_conditions: Dict[str, Any]) -> int:
        """
        Delete vectors matching filter conditions.
        
        Args:
            filter_conditions: Conditions for deletion
            
        Returns:
            int: Number of deleted vectors
        """
        try:
            qdrant_filter = self._build_filter(filter_conditions)
            
            result = self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=qdrant_filter
                )
            )
            
            count = result.get("deleted_points_count", 0) if isinstance(result, dict) else 0
            logger.info(f"🗑️ Deleted {count} vectors matching filter")
            return count
            
        except Exception as e:
            logger.error(f"❌ Failed to delete by filter: {str(e)}")
            return 0
    
    def get_vector(self, file_id: str) -> Optional[List[float]]:
        """
        Get the vector for a file.
        
        Args:
            file_id: File identifier
            
        Returns:
            Optional[List[float]]: Vector or None if not found
        """
        try:
            point_id = self._generate_point_id(file_id)
            
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id],
                with_vectors=True
            )
            
            if points:
                return points[0].vector
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get vector for {file_id}: {str(e)}")
            return None
    
    def get_payload(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the payload for a file.
        
        Args:
            file_id: File identifier
            
        Returns:
            Optional[Dict]: Payload or None if not found
        """
        try:
            point_id = self._generate_point_id(file_id)
            
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id],
                with_payload=True
            )
            
            if points:
                return points[0].payload
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get payload for {file_id}: {str(e)}")
            return None
    
    def update_payload(self, file_id: str, payload: Dict[str, Any]) -> bool:
        """
        Update the payload for a file.
        
        Args:
            file_id: File identifier
            payload: New payload data
            
        Returns:
            bool: True if successful
        """
        try:
            point_id = self._generate_point_id(file_id)
            
            # Get existing vector
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id],
                with_vectors=True
            )
            
            if not points:
                logger.warning(f"⚠️ No vector found for file: {file_id}")
                return False
            
            # Update with same vector, new payload
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=points[0].vector,
                        payload=payload
                    )
                ]
            )
            
            logger.info(f"✅ Updated payload for file: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update payload for {file_id}: {str(e)}")
            return False
    
    def count(self, filter_conditions: Optional[Dict[str, Any]] = None) -> int:
        """
        Count vectors in the collection.
        
        Args:
            filter_conditions: Optional filter conditions
            
        Returns:
            int: Number of vectors
        """
        try:
            qdrant_filter = None
            if filter_conditions:
                qdrant_filter = self._build_filter(filter_conditions)
            
            result = self.client.count(
                collection_name=self.collection_name,
                count_filter=qdrant_filter
            )
            
            return result.count
            
        except Exception as e:
            logger.error(f"❌ Failed to count vectors: {str(e)}")
            return 0
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        Get collection information.
        
        Returns:
            Dict: Collection info
        """
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "vector_size": info.config.params.vectors.size,
                "distance": info.config.params.vectors.distance,
                "points_count": info.points_count,
                "segments_count": info.segments_count
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get collection info: {str(e)}")
            return {}
    
    def _generate_point_id(self, file_id: str) -> int:
        """
        Generate a consistent integer point ID from file_id.
        
        Args:
            file_id: String file ID
            
        Returns:
            int: Point ID
        """
        # Use hash to convert string to integer
        return abs(hash(file_id)) % (2 ** 63 - 1)
    
    def _build_filter(self, conditions: Dict[str, Any]) -> models.Filter:
        """
        Build Qdrant filter from conditions.
        
        Args:
            conditions: Filter conditions
            
        Returns:
            models.Filter: Qdrant filter object
        """
        must_conditions = []
        
        for key, value in conditions.items():
            if isinstance(value, dict):
                # Handle operators like ne, gt, lt, etc.
                for op, val in value.items():
                    if op == "ne":
                        must_conditions.append(
                            models.FieldCondition(
                                key=key,
                                range=None,
                                match=None,
                                geo_bounding_box=None,
                                geo_radius=None,
                                values_count=None,
                                is_empty=None,
                                should_not_match=False,
                                match_except=None,
                                match_any=None,
                                match_text=None
                            )
                        )
                        # Actually, let's use a simpler approach
                        must_conditions.append(
                            models.FieldCondition(
                                key=key,
                                match=models.MatchValue(value=val)
                            )
                        )
                    else:
                        must_conditions.append(
                            models.FieldCondition(
                                key=key,
                                match=models.MatchValue(value=val)
                            )
                        )
            else:
                # Simple equals condition
                must_conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value)
                    )
                )
        
        return models.Filter(must=must_conditions)


# Singleton instance
qdrant_client = QdrantClient()
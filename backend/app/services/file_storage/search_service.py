"""
Search Service - Semantic File Search

Provides semantic search capabilities using:
- SBERT embeddings for query understanding
- Qdrant vector database for similarity search
- PostgreSQL for metadata filtering
"""

import logging
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from ...models.file import File, FileStatus
from ...models.user import User, UserRole
from ...schemas.file import FileSearchQuery, FileSearchResult, FileSearchResponse
from ..embedding_service import embedding_service
from .qdrant_client import qdrant_client

logger = logging.getLogger(__name__)


class SearchService:
    """
    Semantic search service for files.
    """
    
    def __init__(self):
        self.min_score_threshold = 0.1  # Lower threshold to show more results
        self.default_limit = 20
    
    def search(
        self,
        db: Session,
        query: FileSearchQuery,
        user: Optional[User] = None
    ) -> FileSearchResponse:
        """Perform semantic search on files."""
        try:
            logger.info(f"🔍 Searching for: {query.query}")
            logger.info(f"   Department filter: {query.department}")
            
            # 1. Generate embedding for query
            query_embedding = embedding_service.embed_text(query.query)
            if not query_embedding:
                logger.warning("⚠️ Failed to generate query embedding")
                return FileSearchResponse(
                    total=0,
                    results=[],
                    took_ms=0
                )
            
            start_time = time.time()
            
            # 2. Build filter conditions
            filter_conditions = {}
            
            if query.file_type:
                filter_conditions["file_type"] = query.file_type
            
            if query.department:
                filter_conditions["department"] = query.department
            
            # IMPORTANT: DO NOT filter by status - it doesn't exist in Qdrant payload
            # if query.status:
            #     filter_conditions["status"] = query.status
            
            logger.info(f"   Filters: {filter_conditions}")
            
            # 3. Search in Qdrant
            vector_results = qdrant_client.search(
                query_vector=query_embedding,
                limit=query.limit + query.offset + 10,
                score_threshold=0.0,  # Return all results
                filter_conditions=filter_conditions if filter_conditions else None
            )
            
            logger.info(f"📊 Qdrant returned {len(vector_results)} results")
            
            if not vector_results:
                return FileSearchResponse(
                    total=0,
                    results=[],
                    took_ms=(time.time() - start_time) * 1000
                )
            
            # 4. Get file IDs from results
            file_ids = []
            score_map = {}
            for result in vector_results:
                file_id = result['payload'].get('file_id')
                if file_id and file_id not in score_map:
                    file_ids.append(file_id)
                    score_map[file_id] = result['score']
            
            if not file_ids:
                return FileSearchResponse(
                    total=0,
                    results=[],
                    took_ms=(time.time() - start_time) * 1000
                )
            
            logger.info(f"📄 Found {len(file_ids)} unique file IDs")
            
            # 5. Fetch file details from PostgreSQL
            files = db.query(File).filter(
                File.id.in_(file_ids),
                File.status == FileStatus.ACTIVE
            ).all()
            
            logger.info(f"📄 Retrieved {len(files)} files from database")
            
            # 6. Build search results
            results = []
            for file in files:
                file_id_str = str(file.id)
                score = score_map.get(file_id_str, 0.0)
                
                # Apply date filters
                if query.date_from and file.created_at < query.date_from:
                    continue
                if query.date_to and file.created_at > query.date_to:
                    continue
                
                results.append(FileSearchResult(
                    file_id=file.id,
                    filename=file.filename,
                    title=file.title,
                    description=file.description,
                    file_type=file.file_type,
                    department=file.department,
                    score=score,
                    extra_data=file.extra_data or {},
                    created_at=file.created_at
                ))
            
            # 7. Sort by score (highest first)
            results.sort(key=lambda x: x.score, reverse=True)
            
            # 8. Apply pagination
            total = len(results)
            results = results[query.offset:query.offset + query.limit]
            
            took_ms = (time.time() - start_time) * 1000
            
            logger.info(f"✅ Returning {len(results)} results (total: {total})")
            
            return FileSearchResponse(
                total=total,
                results=results,
                took_ms=took_ms
            )
            
        except Exception as e:
            logger.error(f"❌ Search failed: {str(e)}", exc_info=True)
            return FileSearchResponse(
                total=0,
                results=[],
                took_ms=0
            )
    def search_by_keywords(
        self,
        db: Session,
        keywords: List[str],
        file_type: Optional[str] = None,
        department: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Simple keyword-based search (fallback).
        """
        try:
            query = db.query(File).filter(
                File.status == FileStatus.ACTIVE
            )
            
            if file_type:
                query = query.filter(File.file_type == file_type)
            if department:
                query = query.filter(File.department == department)
            
            from sqlalchemy import or_
            conditions = []
            for keyword in keywords:
                keyword_pattern = f"%{keyword}%"
                conditions.append(File.filename.ilike(keyword_pattern))
                conditions.append(File.title.ilike(keyword_pattern))
                conditions.append(File.description.ilike(keyword_pattern))
                conditions.append(File.tags.any(keyword))
            
            if conditions:
                query = query.filter(or_(*conditions))
            
            files = query.limit(limit).all()
            
            return [f.to_dict() for f in files]
            
        except Exception as e:
            logger.error(f"❌ Keyword search failed: {str(e)}")
            return []
    
    def get_similar_files(
        self,
        db: Session,
        file_id: str,
        limit: int = 10,
        exclude_self: bool = True
    ) -> List[FileSearchResult]:
        """
        Find files similar to a given file.
        """
        try:
            results = qdrant_client.search_by_file_id(
                file_id=file_id,
                limit=limit + (1 if exclude_self else 0)
            )
            
            if not results:
                return []
            
            file_ids = []
            score_map = {}
            for result in results:
                fid = result['payload'].get('file_id')
                if fid:
                    if exclude_self and fid == file_id:
                        continue
                    file_ids.append(fid)
                    score_map[fid] = result['score']
            
            if not file_ids:
                return []
            
            files = db.query(File).filter(
                File.id.in_(file_ids),
                File.status == FileStatus.ACTIVE
            ).all()
            
            search_results = []
            for file in files:
                file_id_str = str(file.id)
                search_results.append(FileSearchResult(
                    file_id=file.id,
                    filename=file.filename,
                    title=file.title,
                    description=file.description,
                    file_type=file.file_type,
                    department=file.department,
                    score=score_map.get(file_id_str, 0.0),
                    extra_data=file.extra_data or {},
                    created_at=file.created_at
                ))
            
            search_results.sort(key=lambda x: x.score, reverse=True)
            return search_results[:limit]
            
        except Exception as e:
            logger.error(f"❌ Similar files search failed: {str(e)}")
            return []
    
    def search_by_file_type(
        self,
        db: Session,
        file_type: str,
        department: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search files by type with filters."""
        try:
            query = db.query(File).filter(
                File.file_type == file_type,
                File.status == FileStatus.ACTIVE
            )
            
            if department:
                query = query.filter(File.department == department)
            
            total = query.count()
            files = query.order_by(File.created_at.desc()).offset(offset).limit(limit).all()
            
            return {
                'total': total,
                'files': [f.to_dict() for f in files],
                'limit': limit,
                'offset': offset
            }
            
        except Exception as e:
            logger.error(f"❌ File type search failed: {str(e)}")
            return {'total': 0, 'files': [], 'limit': limit, 'offset': offset}
    
    def get_recent_files(
        self,
        db: Session,
        department: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent files."""
        try:
            query = db.query(File).filter(
                File.status == FileStatus.ACTIVE
            )
            
            if department:
                query = query.filter(File.department == department)
            
            files = query.order_by(File.created_at.desc()).limit(limit).all()
            
            return [f.to_dict() for f in files]
            
        except Exception as e:
            logger.error(f"❌ Recent files search failed: {str(e)}")
            return []
    
    def get_search_suggestions(
        self,
        db: Session,
        query: str,
        limit: int = 5
    ) -> List[str]:
        """Get search suggestions."""
        try:
            suggestions = []
            
            # Get matching file titles
            files = db.query(File).filter(
                File.title.ilike(f"%{query}%"),
                File.status == FileStatus.ACTIVE
            ).limit(limit).all()
            
            for file in files:
                if file.title and file.title.lower() not in [s.lower() for s in suggestions]:
                    suggestions.append(file.title)
            
            # Get matching file types
            file_types = db.query(File.file_type).filter(
                File.file_type.ilike(f"%{query}%"),
                File.status == FileStatus.ACTIVE
            ).distinct().limit(limit).all()
            
            for ft in file_types:
                if ft[0] and ft[0].lower() not in [s.lower() for s in suggestions]:
                    suggestions.append(ft[0])
            
            # Get matching departments
            departments = db.query(File.department).filter(
                File.department.ilike(f"%{query}%"),
                File.status == FileStatus.ACTIVE
            ).distinct().limit(limit).all()
            
            for dept in departments:
                if dept[0] and dept[0].lower() not in [s.lower() for s in suggestions]:
                    suggestions.append(dept[0])
            
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"❌ Search suggestions failed: {str(e)}")
            return []
    
    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        return embedding_service.get_embedding_dimension()


# Singleton instance
search_service = SearchService()
"""
Conversation Retrieval Service

Retrieves authorized human-to-human chat messages for the requesting user
to ground AI Assistant answers in user's accessible conversation history.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from ..models.chat import ChatMessage
from ..models.user import User
from ..services.chat_policy import can_chat, normalize_role
from .institutional_retrieval_service import institutional_retrieval_service

logger = logging.getLogger(__name__)


class ConversationRetrievalService:
    """
    Retrieves authorized P2P chat messages for AI context grounding.
    Strictly enforces authorization: users can ONLY retrieve messages
    where they are either the sender or receiver, AND the conversation
    is allowed per the institutional communication matrix.
    """

    def retrieve_user_conversations(
        self,
        db: Session,
        user: User,
        query_text: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieves matching human-to-human chat messages accessible to the user.
        Only returns messages from conversations the user is authorized to access.
        Uses improved scoring: exact entity match > deadline relevance > sender role > recency.
        """
        if not user or not query_text:
            return []

        clean_query = query_text.lower().strip()
        results: List[Dict[str, Any]] = []

        try:
            # 1. Base query: strictly authorized messages where user is sender or receiver
            # and is_ai is False
            base_query = db.query(ChatMessage).filter(
                ChatMessage.is_ai == False,
                or_(
                    ChatMessage.sender_id == user.id,
                    ChatMessage.receiver_id == user.id
                )
            )

            # Extract specific subject entities or keywords
            specific_entities = institutional_retrieval_service.extract_specific_entities(query_text)

            # Extract search tokens (words >= 2 chars)
            tokens = [w for w in re.findall(r'\b[a-zA-Z0-9_-]{2,}\b', clean_query)
                      if w not in institutional_retrieval_service.GENERIC_QUERY_TERMS]

            # Build search conditions
            search_terms = specific_entities if specific_entities else tokens

            if not search_terms:
                # If query contains no specific terms, return recent non-AI messages
                # but limit to 3 to avoid noise
                candidate_messages = base_query.order_by(desc(ChatMessage.created_at)).limit(10).all()
            else:
                # Search for terms in message content using ILIKE
                conditions = []
                for term in search_terms:
                    escaped = term.replace('%', r'\%').replace('_', r'\_')
                    conditions.append(ChatMessage.content.ilike(f"%{escaped}%"))

                candidate_messages = base_query.filter(or_(*conditions)).order_by(desc(ChatMessage.created_at)).limit(20).all()

            # Track seen source IDs to prevent duplicates
            seen_source_ids = set()

            for msg in candidate_messages:
                # Skip duplicates by source_id
                if msg.id in seen_source_ids:
                    continue
                seen_source_ids.add(msg.id)

                # Authorization check: verify the conversation partner is allowed per chat policy
                partner_id = msg.receiver_id if msg.sender_id == user.id else msg.sender_id
                partner = db.query(User).filter(User.id == partner_id).first()
                if not partner or not can_chat(user, partner)[0]:
                    continue  # Skip messages from unauthorized conversations

                content_lower = (msg.content or "").lower()

                # Calculate relevance score with improved heuristics
                score = 0.5  # Base score for being in the result set

                # --- EXACT ENTITY MATCHING (highest priority) ---
                # Check for exact subject+assignment number matches
                if specific_entities:
                    matched_entities = [e for e in specific_entities if e in content_lower]
                    if not matched_entities and search_terms:
                        # If no specific entities matched, skip - only keep broad token matches below
                        pass  # Will fall through to token scoring

                # --- DEADLINE/DATE RELEVANCE BOOST ---
                # Query asks for a deadline/date; messages containing dates get boost
                has_deadline_term = any(term in content_lower for term in [
                    "deadline", "due date", "submission date", "last date",
                    "submit by", "due on", "scheduled for"
                ])
                has_date_pattern = bool(re.search(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', msg.content)) or \
                                   bool(re.search(r'\b\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\b', content_lower, re.I))

                if has_deadline_term and has_date_pattern:
                    score += 0.3  # Strong boost for explicit deadline + date
                elif has_deadline_term:
                    score += 0.15  # Moderate boost for deadline mentions
                elif has_date_pattern:
                    score += 0.1  # Small boost for any date mention

                # --- ENTITY MATCH BOOST ---
                if specific_entities:
                    matched = [e for e in specific_entities if e in content_lower]
                    score += 0.25 * len(matched)  # Higher weight for exact entity matches

                # --- TOKEN MATCH FALLBACK ---
                if not specific_entities:
                    matched_tokens = [t for t in tokens if t in content_lower]
                    if not matched_tokens:
                        continue
                    score += 0.15 * len(matched_tokens)

                # --- SENDER ROLE BOOST (announcements from authority figures) ---
                # Fetch sender details
                sender = db.query(User).filter(User.id == msg.sender_id).first() if msg.sender_id else None
                sender_role = (sender.role.value if hasattr(sender.role, 'value') else str(sender.role)) if sender else "user"

                # Role hierarchy boost for authoritative announcements
                role_boosts = {
                    "hod": 0.1,
                    "placement_officer": 0.08,
                    "lecturer": 0.06,
                    "admin": 0.05,
                }
                score += role_boosts.get(sender_role, 0)

                created_date_str = msg.created_at.strftime("%d %B %Y") if msg.created_at else ""

                results.append({
                    "source_type": "chat_message",
                    "source_id": msg.id,
                    "title": f"Chat Message from {sender.name if sender else 'Unknown'} ({sender_role})",
                    "sender_id": msg.sender_id,
                    "sender_name": sender.name if sender else "Unknown Sender",
                    "sender_role": sender_role,
                    "receiver_id": msg.receiver_id,
                    "created_at": created_date_str,
                    "content": msg.content,
                    "score": round(score, 2),
                    "has_verified_text": True
                })

            # Sort by score descending, then by recency for ties
            results.sort(key=lambda r: (r["score"], r["created_at"]), reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"❌ Failed to retrieve user conversations: {e}", exc_info=True)
            return []


conversation_retrieval_service = ConversationRetrievalService()

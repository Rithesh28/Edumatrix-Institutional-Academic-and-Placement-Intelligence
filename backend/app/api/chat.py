from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
import logging

from ..core.database import get_db, SessionLocal
from ..core.security import decode_access_token
from .auth import get_current_user
from ..models.user import User, UserRole
from ..models.chat import ChatMessage
from ..schemas.chat import (
    ChatMessageSend,
    ChatMessageResponse,
    ChatConversationResponse,
    AIChatRequest,
    AIChatResponse
)
from ..websocket import manager
from ..services.ai_chat_service import ai_chat_service
from ..services.chat_policy import can_chat, is_ai_allowed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

AI_USER_ID = 0
AI_ASSISTANT_NAME = "EduMatrix AI Assistant"


@router.get("/users")
async def get_chat_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Return only permitted users according to the institutional communication matrix,
    plus the AI Assistant if the user is a student.
    """
    candidates = (
        db.query(User)
        .filter(User.id != current_user.id)
        .filter(User.is_active == True)
        .all()
    )

    permitted_users = [u for u in candidates if can_chat(current_user, u)[0]]

    user_list = [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "department": user.department
        }
        for user in permitted_users
    ]

    # Include AI Assistant at the top strictly for students
    if is_ai_allowed(current_user):
        ai_entry = {
            "id": AI_USER_ID,
            "name": AI_ASSISTANT_NAME,
            "email": "assistant@edumatrix.ai",
            "role": "assistant",
            "is_ai": True
        }
        return [ai_entry] + user_list

    return user_list


@router.get("/conversations", response_model=List[ChatConversationResponse])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all conversations for current user, including AI Assistant conversation for students"""
    conversations = []

    # 1. Check for AI conversation (STUDENTS ONLY)
    if is_ai_allowed(current_user):
        last_ai_message = db.query(ChatMessage).filter(
            ChatMessage.is_ai == True,
            ((ChatMessage.sender_id == current_user.id) | (ChatMessage.receiver_id == current_user.id))
        ).order_by(ChatMessage.created_at.desc()).first()

        if last_ai_message:
            conversations.append(ChatConversationResponse(
                user_id=AI_USER_ID,
                user_name=AI_ASSISTANT_NAME,
                user_role="assistant",
                last_message=last_ai_message.content,
                last_message_time=last_ai_message.created_at,
                unread_count=0,
                is_ai=True
            ))

    # 2. Get unique human users that current user has chatted with
    sent_users = db.query(ChatMessage.receiver_id).filter(
        ChatMessage.sender_id == current_user.id,
        ChatMessage.is_ai == False,
        ChatMessage.receiver_id.isnot(None)
    ).distinct()
    
    received_users = db.query(ChatMessage.sender_id).filter(
        ChatMessage.receiver_id == current_user.id,
        ChatMessage.is_ai == False,
        ChatMessage.sender_id.isnot(None)
    ).distinct()

    all_user_ids = set([u[0] for u in sent_users] + [u[0] for u in received_users])

    for user_id in all_user_ids:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            last_message = db.query(ChatMessage).filter(
                ChatMessage.is_ai == False,
                (
                    ((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == user_id)) |
                    ((ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == current_user.id))
                )
            ).order_by(ChatMessage.created_at.desc()).first()

            unread_count = db.query(ChatMessage).filter(
                ChatMessage.is_ai == False,
                ChatMessage.sender_id == user_id,
                ChatMessage.receiver_id == current_user.id,
                ChatMessage.is_read == False
            ).count()

            conversations.append(ChatConversationResponse(
                user_id=user.id,
                user_name=user.name,
                user_role=user.role.value,
                last_message=last_message.content if last_message else None,
                last_message_time=last_message.created_at if last_message else None,
                unread_count=unread_count,
                is_ai=False
            ))

    return conversations


@router.get("/messages/{user_id}", response_model=List[ChatMessageResponse])
async def get_messages(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat history with specific user or AI assistant"""
    if user_id == AI_USER_ID:
        if not is_ai_allowed(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AI Assistant is only available to students."
            )
        # Return AI chat history
        messages = db.query(ChatMessage).filter(
            ChatMessage.is_ai == True,
            (
                (ChatMessage.sender_id == current_user.id) |
                (ChatMessage.receiver_id == current_user.id)
            )
        ).order_by(ChatMessage.created_at.asc()).all()
        return messages

    # Get human-to-human messages
    messages = db.query(ChatMessage).filter(
        ChatMessage.is_ai == False,
        (
            ((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == user_id)) |
            ((ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == current_user.id))
        )
    ).order_by(ChatMessage.created_at.asc()).all()

    # Mark messages FROM the other user TO current_user as read
    unread_messages = db.query(ChatMessage).filter(
        ChatMessage.is_ai == False,
        ChatMessage.sender_id == user_id,
        ChatMessage.receiver_id == current_user.id,
        ChatMessage.is_read == False
    ).all()

    for msg in unread_messages:
        msg.is_read = True
        msg.read_at = datetime.now()

    if unread_messages:
        db.commit()

    return messages


@router.post("/send", response_model=ChatMessageResponse)
async def send_message(
    message: ChatMessageSend,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send a message. If receiver_id == 0 or is_ai == True, routes to AI Assistant.
    Otherwise verifies institutional communication policy and sends to a human recipient.
    """
    if message.receiver_id == AI_USER_ID or message.is_ai:
        if not is_ai_allowed(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AI Assistant is only available to students."
            )

        # Execute AI Chat Orchestration Pipeline
        ai_result = ai_chat_service.process_user_message(
            db=db,
            user=current_user,
            message=message.content
        )
        ai_response_obj = ai_result["ai_response"]

        # Push AI response to sender if connected via WebSocket
        ws_payload = json.dumps({
            "type": "message",
            "id": ai_response_obj.id,
            "sender_id": AI_USER_ID,
            "receiver_id": current_user.id,
            "content": ai_response_obj.content,
            "is_ai": True,
            "ai_metadata": ai_response_obj.ai_metadata,
            "created_at": ai_response_obj.created_at.isoformat() if ai_response_obj.created_at else None
        })
        await manager.send_personal_message(ws_payload, current_user.id)

        return ai_response_obj

    # Human-to-Human chat
    receiver = db.query(User).filter(User.id == message.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")

    if not receiver.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to message this user."
        )

    allowed, reason = can_chat(current_user, receiver)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to message this user."
        )

    new_message = ChatMessage(
        sender_id=current_user.id,
        receiver_id=message.receiver_id,
        content=message.content,
        is_read=False,
        is_ai=False
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    # Send via WebSocket if receiver is online
    response = json.dumps({
        "type": "message",
        "id": new_message.id,
        "sender_id": new_message.sender_id,
        "receiver_id": new_message.receiver_id,
        "content": new_message.content,
        "is_ai": False,
        "created_at": new_message.created_at.isoformat() if new_message.created_at else None
    })
    await manager.send_personal_message(response, message.receiver_id)

    return new_message


@router.post("/ai", response_model=AIChatResponse)
async def chat_with_ai(
    request: AIChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Dedicated endpoint for interacting with the EduMatrix AI Assistant.
    Returns full grounding metadata and source attribution.
    Only available to students.
    """
    if not is_ai_allowed(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI Assistant is only available to students."
        )

    ai_result = ai_chat_service.process_user_message(
        db=db,
        user=current_user,
        message=request.content
    )

    return AIChatResponse(
        user_message=ChatMessageResponse.model_validate(ai_result["user_message"]),
        ai_response=ChatMessageResponse.model_validate(ai_result["ai_response"]),
        intent=ai_result["intent"],
        intent_confidence=ai_result["intent_confidence"],
        sentiment=ai_result["sentiment"],
        sentiment_confidence=ai_result["sentiment_confidence"],
        retrieval_strategy=ai_result["retrieval_strategy"],
        retrieval_sources=ai_result["retrieval_sources"],
        ai_metadata=ai_result["ai_metadata"]
    )


@router.websocket("/ws/{token}")
async def websocket_chat(websocket: WebSocket, token: str):
    """WebSocket connection for real-time chat with human users and AI assistant"""
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=1008, reason="Invalid token")
        return

    user_id = payload.get("id")
    if user_id is None:
        await websocket.close(code=1008, reason="Invalid user")
        return

    await manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            receiver_id = message_data.get("receiver_id")
            content = message_data.get("content")

            if receiver_id is not None and content:
                db = SessionLocal()
                try:
                    user = db.query(User).filter(User.id == user_id).first()
                    if not user or not user.is_active:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "code": 403,
                            "message": "User account is disabled or not found."
                        }))
                        continue

                    # 1. If message is directed to AI Assistant (receiver_id == 0)
                    if receiver_id == AI_USER_ID or message_data.get("is_ai"):
                        if not is_ai_allowed(user):
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "code": 403,
                                "message": "AI Assistant is only available to students."
                            }))
                            continue

                        ai_result = ai_chat_service.process_user_message(
                            db=db,
                            user=user,
                            message=content
                        )
                        ai_msg = ai_result["ai_response"]

                        # Push AI response back to user
                        ai_response_payload = json.dumps({
                            "type": "message",
                            "id": ai_msg.id,
                            "sender_id": AI_USER_ID,
                            "receiver_id": user_id,
                            "content": ai_msg.content,
                            "is_ai": True,
                            "ai_metadata": ai_msg.ai_metadata,
                            "created_at": ai_msg.created_at.isoformat() if ai_msg.created_at else None
                        })
                        await websocket.send_text(ai_response_payload)

                        # Send sent confirmation
                        await websocket.send_text(json.dumps({
                            "type": "sent",
                            "id": ai_result["user_message"].id,
                            "receiver_id": AI_USER_ID,
                            "content": content,
                            "is_ai": True
                        }))

                    # 2. Human-to-Human message
                    else:
                        receiver = db.query(User).filter(User.id == receiver_id).first()
                        if not receiver:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "code": 404,
                                "message": "Receiver not found."
                            }))
                            continue

                        if not receiver.is_active:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "code": 403,
                                "message": "You are not allowed to message this user."
                            }))
                            continue

                        allowed, reason = can_chat(user, receiver)
                        if not allowed:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "code": 403,
                                "message": "You are not allowed to message this user."
                            }))
                            continue

                        new_message = ChatMessage(
                            sender_id=user_id,
                            receiver_id=receiver_id,
                            content=content,
                            is_read=False,
                            is_ai=False
                        )
                        db.add(new_message)
                        db.commit()
                        db.refresh(new_message)

                        response = json.dumps({
                            "type": "message",
                            "id": new_message.id,
                            "sender_id": new_message.sender_id,
                            "receiver_id": new_message.receiver_id,
                            "content": new_message.content,
                            "is_ai": False,
                            "created_at": new_message.created_at.isoformat() if new_message.created_at else None
                        })
                        await manager.send_personal_message(response, receiver_id)

                        await websocket.send_text(json.dumps({
                            "type": "sent",
                            "id": new_message.id,
                            "receiver_id": receiver_id,
                            "content": content,
                            "is_ai": False
                        }))

                except Exception as ws_err:
                    logger.error(f"❌ WebSocket error processing message: {ws_err}", exc_info=True)
                finally:
                    db.close()

    except WebSocketDisconnect:
        manager.disconnect(user_id)
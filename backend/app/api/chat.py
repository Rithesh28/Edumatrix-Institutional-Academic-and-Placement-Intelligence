from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import json
from ..core.database import get_db
from ..core.security import decode_access_token
from fastapi.security import OAuth2PasswordBearer
from ..models.user import User
from ..models.chat import ChatMessage
from ..schemas.chat import ChatMessageSend, ChatMessageResponse, ChatConversationResponse
from ..websocket import manager

router = APIRouter(prefix="/chat", tags=["Chat"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.get("id")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user
@router.get("/users")
async def get_chat_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Return all users except the currently logged-in user.
    """

    users = (
        db.query(User)
        .filter(User.id != current_user.id)
        .filter(User.is_active == True)
        .all()
    )

    return [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value
        }
        for user in users
    ]

@router.get("/conversations", response_model=List[ChatConversationResponse])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all conversations for current user"""
    
    # Get unique users that current user has chatted with
    sent_users = db.query(ChatMessage.receiver_id).filter(ChatMessage.sender_id == current_user.id).distinct()
    received_users = db.query(ChatMessage.sender_id).filter(ChatMessage.receiver_id == current_user.id).distinct()
    
    all_user_ids = set([u[0] for u in sent_users] + [u[0] for u in received_users])
    
    conversations = []
    for user_id in all_user_ids:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            # Get last message
            last_message = db.query(ChatMessage).filter(
                ((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == user_id)) |
                ((ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == current_user.id))
            ).order_by(ChatMessage.created_at.desc()).first()
            
            # Get unread count (messages sent to current user that are not read)
            unread_count = db.query(ChatMessage).filter(
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
                unread_count=unread_count
            ))
    
    return conversations

@router.get("/messages/{user_id}", response_model=List[ChatMessageResponse])
async def get_messages(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat history with specific user and mark unread messages as read"""
    
    # Get all messages between current_user and the other user
    messages = db.query(ChatMessage).filter(
        ((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == user_id)) |
        ((ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == current_user.id))
    ).order_by(ChatMessage.created_at.asc()).all()
    
    # Mark messages FROM the other user TO current_user as read
    unread_messages = db.query(ChatMessage).filter(
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
    """Send a message to another user"""
    
    # Verify receiver exists
    receiver = db.query(User).filter(User.id == message.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")
    
    # Save to database
    new_message = ChatMessage(
        sender_id=current_user.id,
        receiver_id=message.receiver_id,
        content=message.content,
        is_read=False
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    
    # Try to send via WebSocket if receiver is online
    response = json.dumps({
        "type": "message",
        "id": new_message.id,
        "sender_id": new_message.sender_id,
        "receiver_id": new_message.receiver_id,
        "content": new_message.content,
        "created_at": new_message.created_at.isoformat() if new_message.created_at else None
    })
    
    await manager.send_personal_message(response, message.receiver_id)
    
    return new_message

@router.websocket("/ws/{token}")
async def websocket_chat(websocket: WebSocket, token: str):
    """WebSocket connection for real-time chat"""
    
    # Decode token to get user
    payload = decode_access_token(token)
    
    if payload is None:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    user_id = payload.get("id")
    if user_id is None:
        await websocket.close(code=1008, reason="Invalid user")
        return
    
    # Accept connection
    await manager.connect(user_id, websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            receiver_id = message_data.get("receiver_id")
            content = message_data.get("content")
            
            if receiver_id and content:
                # Save to database
                from ..core.database import SessionLocal
                db = SessionLocal()
                
                new_message = ChatMessage(
                    sender_id=user_id,
                    receiver_id=receiver_id,
                    content=content,
                    is_read=False
                )
                db.add(new_message)
                db.commit()
                db.refresh(new_message)
                db.close()
                
                # Send to receiver if online
                response = json.dumps({
                    "type": "message",
                    "id": new_message.id,
                    "sender_id": new_message.sender_id,
                    "receiver_id": new_message.receiver_id,
                    "content": new_message.content,
                    "created_at": new_message.created_at.isoformat() if new_message.created_at else None
                })
                
                await manager.send_personal_message(response, receiver_id)
                
                # Send confirmation back to sender
                await websocket.send_text(json.dumps({
                    "type": "sent",
                    "id": new_message.id,
                    "receiver_id": receiver_id,
                    "content": content
                }))
                
    except WebSocketDisconnect:
        manager.disconnect(user_id)
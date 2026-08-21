from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ChatMessageSend(BaseModel):
    receiver_id: int
    content: str

class ChatMessageResponse(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatConversationResponse(BaseModel):
    user_id: int
    user_name: str
    user_role: str
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None
    unread_count: int
from typing import Dict, List, Optional
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # active_connections: {user_id: WebSocket}
        self.active_connections: Dict[int, WebSocket] = {}
    
    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"User {user_id} connected. Total active: {len(self.active_connections)}")
    
    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"User {user_id} disconnected. Total active: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, user_id: int):
        """Send message to specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
                return True
            except:
                self.disconnect(user_id)
                return False
        return False
    
    async def broadcast(self, message: str, exclude_user_id: Optional[int] = None):
        """Send message to all connected users except excluded"""
        for user_id, connection in self.active_connections.items():
            if user_id != exclude_user_id:
                try:
                    await connection.send_text(message)
                except:
                    self.disconnect(user_id)

# Singleton instance
manager = ConnectionManager()
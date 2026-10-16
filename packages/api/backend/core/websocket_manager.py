import json
import logging
from typing import Dict

from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages WebSocket connections for real-time task notifications.
    """
    def __init__(self):
        # active_connections: { client_id: WebSocket }
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept connection and store it."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected: {client_id}")

    def disconnect(self, client_id: str):
        """Remove connection from active pool."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket disconnected: {client_id}")

    async def send_personal_message(self, message: dict, client_id: str):
        """Send JSON message to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast(self, message: dict):
        """Send JSON message to all connected clients."""
        payload = json.dumps(message)
        dead_links = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(payload)
            except Exception as e:
                logger.error(f"Broadcast failed for {client_id}: {e}")
                dead_links.append(client_id)

        for client_id in dead_links:
            self.disconnect(client_id)

# Global manager instance
manager = ConnectionManager()

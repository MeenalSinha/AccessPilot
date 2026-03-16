"""
WebSocket Manager — real-time event broadcasting to frontend.
Fix: datetime.utcnow() → datetime.now(timezone.utc).
Fix: Serialiser handles Enum values (AgentStatus is a str-Enum, but be safe).
Fix: send_event catches stale connection and removes it without raising.
"""
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")


class WebSocketManager:
    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self._connections[session_id] = websocket
        logger.info(f"WS connected: {session_id}")
        await self.send_event(session_id, "connected", {"message": "Agent connected"})

    async def disconnect(self, session_id: str):
        self._connections.pop(session_id, None)
        logger.info(f"WS disconnected: {session_id}")

    async def send_event(self, session_id: str, event_type: str, data: dict):
        ws = self._connections.get(session_id)
        if not ws:
            return
        try:
            payload = {
                "event_type": event_type,
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }
            await ws.send_text(json.dumps(payload, default=_json_default))
        except Exception as e:
            logger.warning(f"WS send failed for {session_id}: {e}")
            self._connections.pop(session_id, None)

    async def broadcast_action(self, session_id: str, action_data: dict):
        await self.send_event(session_id, "action", action_data)

    async def broadcast_screenshot(self, session_id: str, screenshot_b64: str, step: int):
        await self.send_event(session_id, "screenshot", {"screenshot": screenshot_b64, "step": step})

    async def broadcast_analysis(self, session_id: str, analysis: dict):
        await self.send_event(session_id, "analysis", analysis)

    async def broadcast_plan(self, session_id: str, plan: dict):
        await self.send_event(session_id, "plan", plan)

    async def broadcast_status(self, session_id: str, status: str, message: str):
        await self.send_event(session_id, "status", {"status": status, "message": message})

    async def broadcast_log(self, session_id: str, level: str, message: str, extra: Optional[dict] = None):
        await self.send_event(session_id, "log", {"level": level, "message": message, "extra": extra or {}})

    async def broadcast_error(self, session_id: str, error: str):
        await self.send_event(session_id, "error", {"error": error})

    async def handle_message(self, session_id: str, msg: dict, session_manager):
        msg_type = msg.get("type")
        if msg_type == "ping":
            await self.send_event(session_id, "pong", {})
        elif msg_type == "stop":
            await session_manager.stop_session(session_id)
            await self.broadcast_status(session_id, "stopped", "Agent stopped by user")
        elif msg_type == "confirm":
            # User approved or denied an irreversible action
            session = session_manager.get_session(session_id)
            if session and session.confirmation_event and session.pending_confirmation is not None:
                session.pending_confirmation["approved"] = bool(msg.get("approved", False))
                session.confirmation_event.set()
                approved = msg.get("approved", False)
                await self.broadcast_log(
                    session_id,
                    "info" if approved else "warning",
                    f"Action {'approved' if approved else 'denied'} by user",
                )
            else:
                logger.debug(f"Received confirm for {session_id} but no pending confirmation")
        else:
            logger.debug(f"Unknown WS message type: {msg_type}")

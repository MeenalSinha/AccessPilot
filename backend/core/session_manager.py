"""
Session Manager — tracks active agent sessions.
Fix: datetime.utcnow() → datetime.now(timezone.utc).
Fix: Session TTL — completed/errored sessions auto-expire after SESSION_TTL_MINUTES.
Fix: list_sessions uses model_dump() (Pydantic v2) with dict() fallback.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from core.models import AgentStatus, TaskPlan

logger = logging.getLogger(__name__)

SESSION_TTL_MINUTES = 60  # completed/error sessions live this long in memory


class AgentSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.task: Optional[TaskPlan] = None
        self.agent_task: Optional[asyncio.Task] = None
        self.is_running = False
        self.screenshots: List[str] = []
        self.action_log: List[dict] = []
        self.created_at: datetime = datetime.now(timezone.utc)
        self.finished_at: Optional[datetime] = None
        # Action confirmation for irreversible actions
        self.pending_confirmation = None  # dict {"approved": bool} written by WS handler
        self.confirmation_event   = None  # asyncio.Event set by WS handler

    def add_screenshot(self, screenshot_b64: str):
        self.screenshots.append(screenshot_b64)
        if len(self.screenshots) > 10:
            self.screenshots = self.screenshots[-10:]

    def get_latest_screenshot(self) -> Optional[str]:
        return self.screenshots[-1] if self.screenshots else None

    def log_action(self, action_data: dict):
        self.action_log.append(action_data)

    def mark_finished(self):
        self.is_running = False
        self.finished_at = datetime.now(timezone.utc)

    def is_expired(self) -> bool:
        if self.is_running:
            return False
        if self.finished_at is None:
            return False
        age = datetime.now(timezone.utc) - self.finished_at
        return age > timedelta(minutes=SESSION_TTL_MINUTES)

    def _task_dict(self) -> Optional[dict]:
        if self.task is None:
            return None
        try:
            return self.task.model_dump()
        except AttributeError:
            return self.task.dict()


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, AgentSession] = {}

    def _evict_expired(self):
        """Remove sessions that have exceeded TTL."""
        expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
        for sid in expired:
            logger.info(f"Evicting expired session: {sid}")
            del self._sessions[sid]

    def create_session(self, session_id: Optional[str] = None) -> AgentSession:
        self._evict_expired()
        if not session_id:
            session_id = str(uuid.uuid4())
        session = AgentSession(session_id)
        self._sessions[session_id] = session
        logger.info(f"Session created: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str) -> AgentSession:
        if session_id not in self._sessions:
            return self.create_session(session_id)
        return self._sessions[session_id]

    async def stop_session(self, session_id: str):
        session = self._sessions.get(session_id)
        if not session:
            return
        session.is_running = False
        if session.agent_task and not session.agent_task.done():
            session.agent_task.cancel()
            try:
                await session.agent_task
            except asyncio.CancelledError:
                pass
        session.mark_finished()
        logger.info(f"Session stopped: {session_id}")

    async def cleanup_all(self):
        for session_id in list(self._sessions.keys()):
            await self.stop_session(session_id)
        self._sessions.clear()

    def list_sessions(self) -> List[dict]:
        self._evict_expired()
        return [
            {
                "session_id": sid,
                "is_running": s.is_running,
                "created_at": s.created_at.isoformat(),
                "task": s._task_dict(),
            }
            for sid, s in self._sessions.items()
        ]
        self.pending_confirmation = None   # dict {"approved": bool}
        self.confirmation_event   = None   # asyncio.Event

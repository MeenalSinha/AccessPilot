"""
Core data models for AccessPilot.
Fix: datetime.utcnow() replaced with datetime.now(timezone.utc) (Python 3.12+).
Fix: model_config allows mutation on TaskPlan so agent can update status/step in-place.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class ActionType(str, Enum):
    CLICK = "CLICK"
    TYPE = "TYPE"
    SCROLL = "SCROLL"
    PRESS = "PRESS"
    WAIT = "WAIT"
    NAVIGATE = "NAVIGATE"
    SCREENSHOT = "SCREENSHOT"
    HOVER = "HOVER"
    SELECT = "SELECT"
    CLEAR = "CLEAR"


class UIElement(BaseModel):
    element_type: str
    label: str = ""
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    confidence: float = 1.0
    description: Optional[str] = None
    interactable: bool = True


class AgentAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    action_type: ActionType
    x: Optional[float] = None
    y: Optional[float] = None
    text: Optional[str] = None
    direction: Optional[str] = None
    key: Optional[str] = None
    seconds: Optional[float] = None
    url: Optional[str] = None
    explanation: str = ""
    timestamp: datetime = Field(default_factory=_utcnow)
    success: Optional[bool] = None
    error: Optional[str] = None


class TaskStep(BaseModel):
    step_number: int
    description: str
    action: Optional[AgentAction] = None
    status: str = "pending"
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None
    reasoning: Optional[str] = None


class TaskPlan(BaseModel):
    model_config = {"arbitrary_types_allowed": True}  # allow mutation

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_command: str
    goal: str
    steps: List[TaskStep] = []
    current_step: int = 0
    status: AgentStatus = AgentStatus.IDLE
    created_at: datetime = Field(default_factory=_utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class ScreenAnalysis(BaseModel):
    ui_elements: List[UIElement] = []
    page_description: str = ""
    current_state: str = ""
    suggested_next_action: Optional[str] = None
    task_progress: float = 0.0
    task_complete: bool = False
    reasoning: str = ""


class CommandRequest(BaseModel):
    command: str
    session_id: Optional[str] = None
    target_url: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class CommandResponse(BaseModel):
    session_id: str
    task_id: str
    status: str
    message: str
    plan: Optional[TaskPlan] = None


# ── Strict validated action schema ────────────────────────────────────────

VALID_ACTION_TYPES = {
    "CLICK", "TYPE", "SCROLL", "PRESS", "WAIT",
    "NAVIGATE", "HOVER", "SELECT", "CLEAR",
}

CONFIDENCE_THRESHOLD = 0.70   # below this → request user confirmation


class ValidatedAction(BaseModel):
    """
    Strict schema for every action produced by the AI layer.
    The automation engine ONLY executes ValidatedAction objects —
    never raw dicts from Gemini. This prevents partial/malformed
    responses from causing unintended browser interactions.
    """
    action_type:      str
    x:                Optional[float] = None
    y:                Optional[float] = None
    text:             Optional[str]   = None
    direction:        Optional[str]   = None
    key:              Optional[str]   = None
    seconds:          Optional[float] = None
    url:              Optional[str]   = None
    # Explainability fields — required
    target:           str  = "Unknown element"
    reason:           str  = "Required to advance the task"
    explanation:      str  = ""
    confidence:       float = 0.85
    grounding_source: str  = "gemini"
    is_irreversible:  bool = False

    @classmethod
    def from_raw(cls, raw: dict) -> "ValidatedAction":
        """
        Parse and validate a raw Gemini response dict.
        Raises ValueError with a clear message if the schema is violated.
        """
        if not isinstance(raw, dict):
            raise ValueError(f"Action must be a JSON object, got {type(raw).__name__}")

        action_type = str(raw.get("action_type", "")).strip().upper()
        if not action_type:
            raise ValueError("action_type is missing or empty")
        if action_type not in VALID_ACTION_TYPES:
            raise ValueError(
                f"action_type '{action_type}' is not valid. "
                f"Must be one of: {sorted(VALID_ACTION_TYPES)}"
            )

        # Validate coordinate types
        x = raw.get("x")
        y = raw.get("y")
        if x is not None:
            try: x = float(x)
            except (TypeError, ValueError):
                raise ValueError(f"x must be a number, got {x!r}")
        if y is not None:
            try: y = float(y)
            except (TypeError, ValueError):
                raise ValueError(f"y must be a number, got {y!r}")

        # CLICK and HOVER require coordinates
        if action_type in ("CLICK", "HOVER") and (x is None or y is None):
            raise ValueError(f"{action_type} requires x and y coordinates")

        # TYPE and PRESS require text/key
        if action_type == "TYPE" and not raw.get("text"):
            raise ValueError("TYPE requires non-empty 'text' field")
        if action_type == "PRESS" and not raw.get("key"):
            raise ValueError("PRESS requires non-empty 'key' field")

        # NAVIGATE requires url
        if action_type == "NAVIGATE":
            url = str(raw.get("url", "")).strip()
            if not url:
                raise ValueError("NAVIGATE requires non-empty 'url' field")
            if not url.startswith(("http://", "https://")):
                raw = dict(raw)
                raw["url"] = "https://" + url

        # Validate confidence
        conf = raw.get("confidence", 0.85)
        try: conf = float(conf)
        except (TypeError, ValueError): conf = 0.85
        conf = max(0.0, min(1.0, conf))

        return cls(
            action_type=action_type,
            x=x, y=y,
            text=raw.get("text"),
            direction=raw.get("direction"),
            key=raw.get("key"),
            seconds=raw.get("seconds"),
            url=raw.get("url"),
            target=str(raw.get("target", "Unknown element"))[:120],
            reason=str(raw.get("reason", "Required to advance the task"))[:300],
            explanation=str(raw.get("explanation", ""))[:300],
            confidence=conf,
            grounding_source=str(raw.get("grounding_source", "gemini")),
            is_irreversible=bool(raw.get("is_irreversible", False)),
        )

    def needs_confirmation(self) -> bool:
        """Returns True when the action should be confirmed by the user."""
        return self.confidence < CONFIDENCE_THRESHOLD or self.is_irreversible

    def to_engine_dict(self) -> dict:
        """Convert to the dict format expected by the automation engine."""
        return {
            "action_type":  self.action_type,
            "x":            self.x,
            "y":            self.y,
            "text":         self.text,
            "direction":    self.direction,
            "key":          self.key,
            "seconds":      self.seconds,
            "url":          self.url,
            "explanation":  self.explanation or self.reason,
            "target":       self.target,
            "reason":       self.reason,
            "grounding_source": self.grounding_source,
            "is_irreversible":  self.is_irreversible,
        }

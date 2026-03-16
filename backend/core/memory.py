"""
Task Memory — structured long-term context for the agent loop.

Replaces the flat list of action strings with a rich TaskMemory object that
carries:
  - task_goal          : the original user command
  - completed_steps    : list of completed step records with outcome + observation
  - last_screen_state  : what was last visible on screen
  - last_action        : the most recent action taken + its result
  - failed_selectors   : coordinates/elements that produced errors (avoid retrying)
  - key_observations   : important facts extracted from screen analysis
  - grounding_hits     : CV-detected elements that were successfully used
  - decision_log       : structured reasoning trail Gemini can reference

This memory is serialised to JSON and injected into every Gemini prompt so the
model always has full task context — not just the last 5 action strings.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class StepRecord:
    step_number: int
    description: str
    action_type: str
    action_target: str          # human-readable target element
    action_explanation: str     # why this action was chosen
    success: bool
    observation: str            # what changed on screen after the action
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TaskMemory:
    """
    Persistent task context injected into every Gemini call.
    Updated after each step in the agent loop.
    """
    task_goal: str
    target_url: str = ""
    current_step_number: int = 0
    completed_steps: List[StepRecord] = field(default_factory=list)
    last_screen_state: str = ""          # page_description from latest analysis
    last_action_type: str = ""
    last_action_target: str = ""
    last_action_success: bool = True
    failed_positions: List[str] = field(default_factory=list)   # "x,y" strings to avoid
    key_observations: List[str] = field(default_factory=list)   # facts extracted from screen
    grounding_hits: List[str] = field(default_factory=list)     # CV element labels used
    decision_log: List[str] = field(default_factory=list)       # Gemini reasoning trail

    # ── Serialisation ──────────────────────────────────────────────────────

    def to_context_string(self, max_steps: int = 8) -> str:
        """
        Serialise memory to a compact JSON string suitable for prompt injection.
        Keeps the most recent `max_steps` completed steps.
        """
        recent = self.completed_steps[-max_steps:]
        return json.dumps({
            "task_goal": self.task_goal,
            "current_step_number": self.current_step_number,
            "last_screen_state": self.last_screen_state,
            "last_action": {
                "type": self.last_action_type,
                "target": self.last_action_target,
                "success": self.last_action_success,
            },
            "completed_steps": [
                {
                    "step": s.step_number,
                    "action": s.action_type,
                    "target": s.action_target,
                    "success": s.success,
                    "observation": s.observation,
                }
                for s in recent
            ],
            "key_observations": self.key_observations[-5:],
            "failed_positions": self.failed_positions[-10:],
            "grounding_hits": self.grounding_hits[-5:],
        }, indent=None, ensure_ascii=False)

    def to_summary_string(self) -> str:
        """One-line summary for logging."""
        done = len(self.completed_steps)
        ok   = sum(1 for s in self.completed_steps if s.success)
        return (
            f"goal='{self.task_goal[:50]}' "
            f"step={self.current_step_number} "
            f"completed={done}(ok={ok}) "
            f"last={self.last_action_type}"
        )

    # ── Mutators ───────────────────────────────────────────────────────────

    def record_step(
        self,
        step_number: int,
        description: str,
        action_type: str,
        action_target: str,
        action_explanation: str,
        success: bool,
        observation: str,
    ):
        """Called after each action execution to update memory."""
        record = StepRecord(
            step_number=step_number,
            description=description,
            action_type=action_type,
            action_target=action_target,
            action_explanation=action_explanation,
            success=success,
            observation=observation,
        )
        self.completed_steps.append(record)
        self.last_action_type    = action_type
        self.last_action_target  = action_target
        self.last_action_success = success
        self.current_step_number = step_number

        if not success:
            # Remember bad positions to avoid retrying them
            if action_type in ("CLICK", "HOVER") and action_target:
                self.failed_positions.append(action_target)

    def add_observation(self, obs: str):
        """Add a key fact extracted from screen analysis."""
        if obs and obs not in self.key_observations:
            self.key_observations.append(obs[:200])

    def add_decision(self, reasoning: str):
        """Record Gemini's reasoning for this step."""
        if reasoning:
            self.decision_log.append(reasoning[:300])

    def add_grounding_hit(self, label: str):
        """Record a CV element that was successfully used."""
        if label and label not in self.grounding_hits:
            self.grounding_hits.append(label)

    def update_screen_state(self, page_description: str, current_state: str):
        self.last_screen_state = f"{page_description} [{current_state}]"

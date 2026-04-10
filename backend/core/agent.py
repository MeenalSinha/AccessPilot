"""
Agent Orchestrator — feedback loop with:
  1. TaskMemory — structured long-term context injected into every Gemini call
  2. Explainable Actions — target, reason, grounding_source, confidence in every action
  3. Vision Grounding — CV + Gemini cross-referenced for higher-confidence coordinates
  4. Action Confirmation — irreversible actions pause and wait for user approval via WS
  5. Timeout, cleanup, error recovery all preserved
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.gemini_client import (
    analyze_screen,
    create_task_plan,
    generate_next_action,
    recover_from_error,
    ground_cv_elements,
)
from core.memory import TaskMemory, StepRecord
from core.self_healing import SelfHealingEngine
from core.models import AgentAction, AgentStatus, TaskPlan, TaskStep, ValidatedAction, CONFIDENCE_THRESHOLD
from core.session_manager import AgentSession
from core.websocket_manager import WebSocketManager
from engine.automation import engine as automation_engine
from vision.cv_engine import annotate_screenshot, detect_interactive_regions

logger = logging.getLogger(__name__)

MAX_STEPS             = 30
MAX_RETRIES           = 3
STEP_DELAY            = 0.8
TASK_TIMEOUT_SECONDS  = 600
CONFIRM_TIMEOUT       = 30.0   # seconds to wait for user confirmation


def _plan_dict(plan: TaskPlan) -> dict:
    try:
        return plan.model_dump()
    except AttributeError:
        return plan.dict()


class AgentOrchestrator:
    def __init__(self, ws_manager: WebSocketManager):
        self.ws = ws_manager

    # ── Public entry ───────────────────────────────────────────────────────
    async def run_task(
        self,
        session: AgentSession,
        command: str,
        target_url: Optional[str] = None,
        context: Optional[Dict] = None,
    ):
        try:
            await asyncio.wait_for(
                self._run_task(session, command, target_url, context),
                timeout=TASK_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(f"[{session.session_id}] Task timed out after {TASK_TIMEOUT_SECONDS}s")
            if session.task:
                session.task.status = AgentStatus.ERROR
                session.task.error  = f"Task timed out after {TASK_TIMEOUT_SECONDS}s"
            await self.ws.broadcast_status(
                session.session_id, "error",
                f"Task timed out after {TASK_TIMEOUT_SECONDS // 60} minutes",
            )
            session.mark_finished()

    # ── Inner loop ─────────────────────────────────────────────────────────
    async def _run_task(
        self,
        session: AgentSession,
        command: str,
        target_url: Optional[str] = None,
        context: Optional[Dict] = None,
    ):
        sid            = session.session_id
        retry_count    = 0
        task: Optional[TaskPlan] = None
        browser_session = None

        # ── Initialise task memory + self-healing engine ──────────────────
        memory = TaskMemory(
            task_goal=command,
            target_url=target_url or "",
        )
        healer = SelfHealingEngine(self.ws, sid)

        try:
            await self.ws.broadcast_status(sid, "planning", "Creating task plan...")

            # ── 1. Plan ────────────────────────────────────────────────────
            try:
                plan_data = await create_task_plan(command, target_url or "")
            except Exception as e:
                logger.error(f"[{sid}] Planning failed: {e}")
                await self.ws.broadcast_error(sid, f"Planning failed: {e}")
                return

            task = TaskPlan(
                user_command=command,
                goal=plan_data.get("goal", command),
                steps=[
                    TaskStep(
                        step_number=s["step_number"],
                        description=s["description"],
                        reasoning=s.get("reasoning", ""),
                    )
                    for s in plan_data.get("steps", [])
                ],
                status=AgentStatus.RUNNING,
            )
            session.task = task
            # Persist plan to DB immediately
            from core.database import save_session
            await save_session(sid, session.is_running, session._task_dict() or {}, None)

            # Broadcast plan with irreversible step info for UI warning
            plan_payload = _plan_dict(task)
            plan_payload["irreversible_actions"] = plan_data.get("irreversible_actions", [])
            plan_payload["success_criteria"]     = plan_data.get("success_criteria", "")
            await self.ws.broadcast_plan(sid, plan_payload)
            logger.info(f"[{sid}] Plan: {len(task.steps)} steps — {task.goal[:60]}")
            await self.ws.broadcast_log(sid, "info", f"Plan: {task.goal}")

            # ── 2. Browser ─────────────────────────────────────────────────
            browser_session = await automation_engine.create_session(sid, headless=True)

            if target_url:
                nav = await browser_session.execute_action({
                    "action_type": "NAVIGATE",
                    "url": target_url,
                    "explanation": f"Opening {target_url}",
                })
                # Log to DB
                await session.log_action({
                    "step": 0,
                    "action_type": "NAVIGATE",
                    "url": target_url,
                    "success": nav.get("success", False),
                    "message": nav.get("message", "")
                })
                lvl = "info" if nav.get("success") else "warning"
                await self.ws.broadcast_log(sid, lvl, nav.get("message", ""))

            # ── 3. Agent loop ───────────────────────────────────────────────
            step_count = 0
            while session.is_running and step_count < MAX_STEPS:
                step_count += 1
                await self.ws.broadcast_status(sid, "running", f"Step {step_count}")

                # Capture screenshot
                screenshot_b64 = await browser_session.take_screenshot()
                session.add_screenshot(screenshot_b64)

                current_step_desc = (
                    task.steps[task.current_step].description
                    if task.steps and task.current_step < len(task.steps)
                    else "Completing task"
                )

                # ── CV detection ────────────────────────────────────────
                cv_regions = detect_interactive_regions(screenshot_b64)

                # ── Gemini screen analysis with memory ──────────────────
                try:
                    analysis = await analyze_screen(
                        screenshot_b64=screenshot_b64,
                        task_goal=task.goal,
                        current_step=current_step_desc,
                        previous_actions=[],   # preserved for compatibility, but memory.to_context_string() is primary
                        task_memory_context=memory.to_context_string(),
                    )
                except Exception as e:
                    logger.error(f"[{sid}] step={step_count} analysis error: {e}")
                    analysis = {
                        "ui_elements": [], "page_description": "Analysis failed",
                        "task_complete": False, "task_progress": 0,
                        "reasoning": str(e), "suggested_next_action": "Wait",
                        "current_state": "unknown", "key_observation": "",
                    }

                # Update memory with screen state
                memory.update_screen_state(
                    analysis.get("page_description", ""),
                    analysis.get("current_state", ""),
                )
                if analysis.get("key_observation"):
                    memory.add_observation(analysis["key_observation"])
                if analysis.get("reasoning"):
                    memory.add_decision(analysis["reasoning"])

                # ── Vision grounding ────────────────────────────────────
                grounded = ground_cv_elements(
                    cv_regions,
                    analysis.get("ui_elements", []),
                    browser_session.viewport_width,
                    browser_session.viewport_height,
                )
                # Record successful groundings in memory
                for g in grounded:
                    if g["iou_with_gemini"] > 0.2:
                        memory.add_grounding_hit(g["label"])

                # Annotate screenshot with both Gemini elements + grounded CV regions
                annotated = annotate_screenshot(
                    screenshot_b64, analysis.get("ui_elements", [])
                )

                await self.ws.broadcast_screenshot(sid, annotated or screenshot_b64, step_count)
                await self.ws.broadcast_analysis(sid, {
                    "analysis":          analysis,
                    "cv_regions_count":  len(cv_regions),
                    "grounded_count":    len(grounded),
                    "step":              step_count,
                    "memory_summary":    memory.to_summary_string(),
                })

                # ── Completion check ────────────────────────────────────
                if analysis.get("task_complete") or analysis.get("task_progress", 0) >= 0.95:
                    task.status      = AgentStatus.COMPLETED
                    task.completed_at = datetime.now(timezone.utc)
                    logger.info(f"[{sid}] Task completed at step {step_count}")
                    await self.ws.broadcast_status(sid, "completed", "Task completed successfully")
                    await self.ws.broadcast_log(sid, "success", "Task completed")
                    break

                # ── Generate action with memory + vision grounding ───────
                try:
                    action_data = await generate_next_action(
                        screenshot_b64=screenshot_b64,
                        screen_description=analysis.get("page_description", ""),
                        ui_elements=analysis.get("ui_elements", []),
                        task_goal=task.goal,
                        current_step_description=current_step_desc,
                        previous_actions=[],  # memory is primary
                        screen_width=browser_session.viewport_width,
                        screen_height=browser_session.viewport_height,
                        cv_regions=cv_regions,
                        task_memory_context=memory.to_context_string(),
                    )
                except Exception as e:
                    action_data = {
                        "action_type": "WAIT", "seconds": 2,
                        "target": "page",
                        "reason": f"Generation error — waiting: {e}",
                        "explanation": f"Generation error: {e}",
                        "confidence": 0.5,
                        "grounding_source": "none",
                        "is_irreversible": False,
                    }

                # ── Strict schema validation ─────────────────────────────
                # The engine only ever executes a ValidatedAction — never
                # a raw dict. This prevents malformed Gemini responses from
                # causing unintended browser interactions.
                try:
                    validated = ValidatedAction.from_raw(action_data)
                except ValueError as schema_err:
                    await self.ws.broadcast_log(
                        sid, "warning",
                        f"Action schema validation failed: {schema_err} — falling back to WAIT",
                    )
                    validated = ValidatedAction(
                        action_type="WAIT", seconds=2,
                        target="page",
                        reason=f"Schema validation failed: {schema_err}",
                        explanation=f"Waiting after schema error: {schema_err}",
                        confidence=0.5,
                    )

                # ── Confidence threshold + irreversible check ────────────
                # If confidence < CONFIDENCE_THRESHOLD OR action is irreversible
                # → pause and request user confirmation.
                if validated.needs_confirmation():
                    conf_pct = f"{validated.confidence:.0%}"
                    if validated.confidence < CONFIDENCE_THRESHOLD:
                        confirm_msg = (
                            f"Low confidence ({conf_pct}): agent thinks this is the "
                            f"'{validated.target}'. Should I proceed?"
                        )
                    else:
                        confirm_msg = (
                            f"This action ({validated.action_type} on "
                            f"'{validated.target}') cannot be undone. Proceed?"
                        )
                    confirmed = await self._request_confirmation(
                        sid=sid,
                        action_type=validated.action_type,
                        target=validated.target,
                        reason=validated.reason,
                        session=session,
                        message=confirm_msg,
                        confidence=validated.confidence,
                    )
                    if not confirmed:
                        await self.ws.broadcast_log(
                            sid, "warning",
                            f"Action [{validated.action_type}] on '{validated.target}' "
                            f"(confidence={conf_pct}) was not confirmed — skipping",
                        )
                        if task.steps:
                            task.current_step = min(
                                max(0, task.current_step + 1), len(task.steps) - 1
                            )
                        await asyncio.sleep(STEP_DELAY)
                        continue

                action = AgentAction(
                    action_type=validated.action_type,
                    x=validated.x,
                    y=validated.y,
                    text=validated.text,
                    direction=validated.direction,
                    key=validated.key,
                    seconds=validated.seconds,
                    url=validated.url,
                    explanation=validated.explanation or validated.reason,
                )

                # Broadcast full explainable action
                await self.ws.broadcast_action(sid, {
                    "action":            action.model_dump() if hasattr(action, "model_dump") else action.dict(),
                    "step":              step_count,
                    "target":            validated.target,
                    "reason":            validated.reason,
                    "explanation":       validated.explanation or validated.reason,
                    "confidence":        validated.confidence,
                    "grounding_source":  validated.grounding_source,
                    "is_irreversible":   validated.is_irreversible,
                    "needs_confirm":     validated.needs_confirmation(),
                    "analysis_summary":  analysis.get("suggested_next_action", ""),
                    "reasoning":         analysis.get("reasoning", ""),
                    "memory_summary":    memory.to_summary_string(),
                })

                # ── Execute using validated engine dict ──────────────────
                exec_result = await browser_session.execute_action(validated.to_engine_dict())
                action.success = exec_result.get("success", False)
                
                # Persistent Log
                await session.log_action({
                    "step": step_count,
                    "action_type": validated.action_type,
                    "target": validated.target,
                    "explanation": validated.explanation or validated.reason,
                    "success": action.success,
                    "confidence": validated.confidence,
                    "grounding_source": validated.grounding_source,
                    "result": exec_result
                })

                logger.info(
                    f"[{sid}] step={step_count} action={action.action_type} "
                    f"target='{validated.target}' conf={validated.confidence:.2f} "
                    f"success={action.success}"
                )
                await self.ws.broadcast_log(
                    sid,
                    "info" if action.success else "warning",
                    f"[{action.action_type}] {validated.explanation or validated.reason}",
                    {"result": exec_result, "target": validated.target,
                     "confidence": validated.confidence},
                )

                # ── Update memory after execution ───────────────────────
                obs = (
                    f"Action {validated.action_type} on '{validated.target}' "
                    f"{'succeeded' if action.success else 'failed'}: {exec_result.get('message','')}"
                )
                memory.record_step(
                    step_number=step_count,
                    description=current_step_desc,
                    action_type=str(validated.action_type),
                    action_target=validated.target,
                    action_explanation=validated.explanation or validated.reason,
                    success=action.success,
                    observation=obs,
                )

                # ── Error recovery — self-healing strategy chain ────────
                if not action.success:
                    retry_count += 1
                    await self.ws.broadcast_log(
                        sid, "warning",
                        f"Action failed (attempt {retry_count}/{MAX_RETRIES}): "
                        f"{exec_result.get('message', '')}",
                    )

                    # Strategy 1 → scroll, Strategy 2 → text-similarity, Strategy 3 → ask user
                    heal_action = await healer.attempt(
                        failed_action=validated.to_engine_dict(),
                        exec_result=exec_result,
                        ui_elements=analysis.get("ui_elements", []),
                        cv_regions=cv_regions,
                        memory_context=memory.to_context_string(),
                        screen_width=browser_session.viewport_width,
                        screen_height=browser_session.viewport_height,
                    )
                    h_result = await browser_session.execute_action(heal_action)
                    memory.record_step(
                        step_number=step_count,
                        description=f"Self-heal: {heal_action.get('heal_strategy', 'unknown')}",
                        action_type=heal_action.get("action_type", "WAIT"),
                        action_target=heal_action.get("target", "page"),
                        action_explanation=heal_action.get("heal_message", ""),
                        success=h_result.get("success", False),
                        observation=f"Heal result: {h_result.get('message', '')}",
                    )

                    if retry_count >= MAX_RETRIES:
                        # Self-healing exhausted — escalate to Gemini deep recovery
                        fresh_shot = await browser_session.take_screenshot()
                        recovery   = await recover_from_error(
                            screenshot_b64=fresh_shot,
                            error=exec_result.get("message", "Unknown error"),
                            screen_description=analysis.get("page_description", ""),
                            task_goal=task.goal,
                            previous_actions=[],
                            task_memory_context=memory.to_context_string(),
                        )
                        diagnosis = recovery.get("diagnosis", "Unknown issue")
                        logger.warning(f"[{sid}] Gemini recovery: {diagnosis}")
                        await self.ws.broadcast_log(
                            sid, "warning",
                            f"Gemini recovery: {diagnosis}",
                            {"recovery": recovery},
                        )

                        if recovery.get("abort_recommended"):
                            task.status = AgentStatus.ERROR
                            task.error  = diagnosis
                            await self.ws.broadcast_status(sid, "error", f"Task aborted: {diagnosis}")
                            break

                        ra = recovery.get("recovery_action", {})
                        if ra.get("action_type"):
                            r_result = await browser_session.execute_action(ra)
                            await self.ws.broadcast_log(
                                sid,
                                "info" if r_result.get("success") else "warning",
                                f"[RECOVERY] {ra.get('explanation', '')}",
                                {"result": r_result},
                            )
                            memory.record_step(
                                step_number=step_count,
                                description="Gemini deep recovery",
                                action_type=ra.get("action_type", "WAIT"),
                                action_target=ra.get("target", ""),
                                action_explanation=ra.get("explanation", ""),
                                success=r_result.get("success", False),
                                observation=f"Gemini recovery: {r_result.get('message', '')}",
                            )

                        retry_count = 0
                else:
                    retry_count = 0

                # Advance plan step
                if task.steps:
                    task.current_step = min(
                        max(0, task.current_step + 1), len(task.steps) - 1
                    )

                await asyncio.sleep(STEP_DELAY)

            # Max steps exhausted
            if session.is_running and task and task.status == AgentStatus.RUNNING:
                task.status = AgentStatus.ERROR
                task.error  = f"Max steps ({MAX_STEPS}) reached without completion"
                await self.ws.broadcast_status(sid, "error", task.error)

        except asyncio.CancelledError:
            logger.info(f"[{sid}] Task cancelled")
            if task:
                task.status = AgentStatus.ERROR
                task.error  = "Cancelled"
            raise

        except Exception as e:
            logger.error(f"[{sid}] Unhandled error: {e}", exc_info=True)
            if task:
                task.status = AgentStatus.ERROR
                task.error  = str(e)
            await self.ws.broadcast_error(sid, str(e))

        finally:
            if browser_session is not None:
                await automation_engine.stop_session(sid)
            session.mark_finished()
            logger.info(
                f"[{sid}] Finished — status={task.status if task else 'no_task'} "
                f"memory={memory.to_summary_string()}"
            )

    # ── Action Confirmation ─────────────────────────────────────────────────
    async def _request_confirmation(
        self,
        sid: str,
        action_type: str,
        target: str,
        reason: str,
        session: AgentSession,
        message: str = "",
        confidence: float = 1.0,
    ) -> bool:
        """
        Pause for low-confidence OR irreversible actions and wait for user approval.

        Triggered when:
          - confidence < CONFIDENCE_THRESHOLD (0.70): agent is unsure which element to use
          - is_irreversible=True: action cannot be undone (payment, delete, send)

        Sends 'confirm_required' WS event. Frontend must reply with
        {'type': 'confirm', 'approved': true/false} within CONFIRM_TIMEOUT seconds.
        """
        confirm_event = asyncio.Event()
        confirm_result: Dict[str, Any] = {"approved": False}

        session.pending_confirmation = confirm_result
        session.confirmation_event   = confirm_event

        await self.ws.send_event(sid, "confirm_required", {
            "action_type": action_type,
            "target":      target,
            "reason":      reason,
            "confidence":  round(confidence, 3),
            "message":     message or f"Agent wants to {action_type} on '{target}'. Proceed?",
            "timeout":     CONFIRM_TIMEOUT,
            "low_confidence": confidence < CONFIDENCE_THRESHOLD,
        })

        try:
            await asyncio.wait_for(confirm_event.wait(), timeout=CONFIRM_TIMEOUT)
        except asyncio.TimeoutError:
            await self.ws.broadcast_log(
                sid, "warning",
                f"Confirmation timed out after {CONFIRM_TIMEOUT:.0f}s — action skipped",
            )
            return False
        finally:
            session.pending_confirmation = None
            session.confirmation_event   = None

        return bool(confirm_result.get("approved", False))

"""
Gemini AI Layer — Visual understanding, planning, and action generation.

Key improvements in this version:
1. Structured Explainable Action JSON — every action includes:
     action_type, target (which element), reason (why), confidence, grounding_source
2. Task Memory injection — full TaskMemory context in every prompt so Gemini
   maintains long-term context across steps
3. Vision Grounding — CV-detected elements are cross-referenced with Gemini's
   reasoning to produce higher-confidence action targets
4. All prompts validated: {{ }} escaping on JSON examples
"""
import base64
import json
import logging
import os
import re
from io import BytesIO
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Vertex AI lazy init ────────────────────────────────────────────────────
_gemini_vision_model = None
_gemini_text_model   = None
_vertex_init_done    = False


def _ensure_vertex_init() -> bool:
    global _gemini_vision_model, _gemini_text_model, _vertex_init_done
    if _vertex_init_done:
        return _gemini_vision_model is not None

    _vertex_init_done = True
    project  = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    if not project or project in ("your-project-id", ""):
        logger.error("GOOGLE_CLOUD_PROJECT not set — Production mode REQUIRES a valid GCP Project ID.")
        return False

    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        vertexai.init(project=project, location=location)
        _gemini_vision_model = GenerativeModel("gemini-1.5-pro")
        _gemini_text_model   = GenerativeModel("gemini-1.5-pro")
        logger.info(f"Vertex AI successfully initialized — project={project} location={location}")
        return True
    except Exception as exc:
        logger.error(f"Vertex AI initialization failed: {exc}")
        return False


def is_demo_mode() -> bool:
    return not _ensure_vertex_init()


# ── Prompt templates ───────────────────────────────────────────────────────

SCREEN_ANALYSIS_PROMPT = """\
You are AccessPilot, an expert UI automation agent.

Analyze this screenshot carefully and return a JSON object with EXACTLY this structure:
{{
  "page_description": "brief description of what is shown on screen",
  "current_state": "what state the UI is in",
  "ui_elements": [
    {{
      "element_type": "button|input|link|menu|table|icon|text|dropdown|checkbox|image",
      "label": "visible text or aria-label",
      "x": 0.0,
      "y": 0.0,
      "width": 0.0,
      "height": 0.0,
      "confidence": 0.9,
      "description": "what this element does",
      "interactable": true
    }}
  ],
  "task_progress": 0.0,
  "task_complete": false,
  "reasoning": "your reasoning about what you see and what to do next",
  "suggested_next_action": "human-readable description of the next best action",
  "key_observation": "one important fact extracted from this screen for memory"
}}

x, y, width, height are percentages (0-100) of screen dimensions.
task_progress is 0.0 to 1.0.

Current task goal: {task_goal}
Current step: {current_step}
Task memory context: {task_memory}

Return ONLY valid JSON. No markdown, no explanation outside the JSON.
"""

TASK_PLANNING_PROMPT = """\
You are AccessPilot, an expert UI automation agent. Break down this user command into a precise step-by-step plan.

User command: {command}
Target URL or context: {context}

Return a JSON object with EXACTLY this structure:
{{
  "goal": "concise description of the overall goal",
  "steps": [
    {{
      "step_number": 1,
      "description": "human-readable description of this step",
      "reasoning": "why this step is needed",
      "expected_outcome": "what should be visible/true after this step",
      "is_irreversible": false
    }}
  ],
  "estimated_steps": 5,
  "risk_factors": ["potential issues to watch for"],
  "success_criteria": "how to know the task is complete",
  "irreversible_actions": ["any steps that cannot be undone"]
}}

Be specific. Assume you are controlling a real browser.
Mark any step that submits payments, deletes data, sends emails, or makes purchases as is_irreversible: true.
Return ONLY valid JSON.
"""

ACTION_GENERATION_PROMPT = """\
You are AccessPilot, an expert UI automation agent generating precise browser actions.

TASK MEMORY (full context):
{task_memory}

Current screenshot shows: {screen_description}
UI elements detected by Gemini: {ui_elements}
CV-grounded elements (from OpenCV — use these coordinates when available): {cv_grounded}
Current task goal: {task_goal}
Current step: {current_step_description}

Generate the SINGLE best next action. Return a JSON object:
{{
  "action_type": "CLICK|TYPE|SCROLL|PRESS|WAIT|NAVIGATE|HOVER|SELECT|CLEAR",
  "x": null,
  "y": null,
  "text": null,
  "direction": null,
  "key": null,
  "seconds": null,
  "url": null,
  "target": "human-readable name of the element being acted on (e.g. 'Search button', 'Email input field')",
  "reason": "why this specific action is required to advance the task goal",
  "explanation": "concise combined description: action + target + reason",
  "confidence": 0.9,
  "grounding_source": "gemini|cv|combined",
  "is_irreversible": false
}}

x, y are percentages (0-100) of screen dimensions, or null.
Set grounding_source to 'cv' when using cv_grounded coordinates, 'gemini' when using Gemini-detected elements, 'combined' when both agree.
Set is_irreversible: true only for payment submissions, deletions, sends, purchases.
Return ONLY valid JSON.
"""

ERROR_RECOVERY_PROMPT = """\
AccessPilot encountered an issue. Analyze the situation and suggest recovery.

Error that occurred: {error}
Current screenshot shows: {screen_description}
Task goal: {task_goal}
Task memory context: {task_memory}

Return a JSON object:
{{
  "diagnosis": "what went wrong and why",
  "recovery_action": {{
    "action_type": "CLICK|TYPE|SCROLL|PRESS|WAIT|NAVIGATE",
    "x": null,
    "y": null,
    "text": null,
    "url": null,
    "target": "what element to interact with for recovery",
    "reason": "why this recovery action will fix the issue",
    "explanation": "recovery action explanation"
  }},
  "alternative_approach": "if the recovery fails, try this instead",
  "abort_recommended": false
}}

Return ONLY valid JSON.
"""


# ── JSON extraction ────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*",     "", text)
    text = text.strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    raise ValueError(f"No JSON found in response: {text[:200]}")


# ── Screenshot compression ─────────────────────────────────────────────────

def _compress_screenshot(screenshot_b64: str, max_width: int = 1280, quality: int = 75) -> str:
    try:
        from PIL import Image
        raw = base64.b64decode(screenshot_b64)
        img = Image.open(BytesIO(raw))
        if img.width > max_width:
            img = img.resize(
                (max_width, int(img.height * max_width / img.width)),
                Image.LANCZOS,
            )
        buf = BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return screenshot_b64


# ── Vision Grounding helper ────────────────────────────────────────────────

def ground_cv_elements(
    cv_regions: List[Dict],
    ui_elements: List[Dict],
    screen_width: int = 1280,
    screen_height: int = 800,
) -> List[Dict]:
    """
    Cross-reference OpenCV-detected regions with Gemini-identified elements.
    Returns a list of grounded elements with pixel coordinates and labels.

    A CV region is 'grounded' when it spatially overlaps with a Gemini element
    (IoU > 0.2). Grounded elements carry higher confidence because both systems
    agree on the location.
    """
    def pct_to_px(el: Dict) -> tuple:
        """Convert percentage coords to pixels."""
        cx = el.get("x", 50) / 100 * screen_width
        cy = el.get("y", 50) / 100 * screen_height
        w  = el.get("width", 10) / 100 * screen_width
        h  = el.get("height", 5) / 100 * screen_height
        return cx, cy, w, h

    def overlap(cx1, cy1, w1, h1, cx2, cy2, w2, h2) -> float:
        x1l, x1r = cx1 - w1/2, cx1 + w1/2
        y1t, y1b = cy1 - h1/2, cy1 + h1/2
        x2l, x2r = cx2 - w2/2, cx2 + w2/2
        y2t, y2b = cy2 - h2/2, cy2 + h2/2
        iw = max(0, min(x1r, x2r) - max(x1l, x2l))
        ih = max(0, min(y1b, y2b) - max(y1t, y2t))
        inter = iw * ih
        union = w1*h1 + w2*h2 - inter
        return inter / union if union > 0 else 0.0

    grounded = []

    for cv in cv_regions:
        cx_cv, cy_cv, w_cv, h_cv = pct_to_px(cv)
        # Convert CV bbox list format if needed
        if "bbox" in cv:
            bx, by, bw, bh = cv["bbox"]
            cx_cv = bx + bw/2
            cy_cv = by + bh/2
            w_cv, h_cv = float(bw), float(bh)

        best_iou   = 0.0
        best_label = cv.get("element_type", "element")

        for el in ui_elements:
            cx_el, cy_el, w_el, h_el = pct_to_px(el)
            iou = overlap(cx_cv, cy_cv, w_cv, h_cv, cx_el, cy_el, w_el, h_el)
            if iou > best_iou:
                best_iou   = iou
                best_label = el.get("label", el.get("element_type", "element"))

        confidence = round(min(0.95, cv.get("confidence", 0.65) + (0.15 if best_iou > 0.2 else 0)), 2)
        grounded.append({
            "label":          best_label,
            "element_type":   cv.get("element_type", "element"),
            "x_px":           round(cx_cv),
            "y_px":           round(cy_cv),
            "x_pct":          round(cx_cv / screen_width * 100, 1),
            "y_pct":          round(cy_cv / screen_height * 100, 1),
            "confidence":     confidence,
            "iou_with_gemini": round(best_iou, 3),
            "source":         "combined" if best_iou > 0.2 else "cv_only",
        })

    # Sort by confidence descending
    return sorted(grounded, key=lambda e: -e["confidence"])[:10]


# ── Real Gemini calls ──────────────────────────────────────────────────────

async def _call_gemini_vision(prompt: str, screenshot_b64: str) -> str:
    if not _ensure_vertex_init():
        from core.emulated_ai import emulated_vision_response
        logger.warning("Vertex AI not configured — falling back to Emulated AI (Demo Mode)")
        return emulated_vision_response(prompt, screenshot_b64)
    try:
        from vertexai.generative_models import Part
        compressed   = _compress_screenshot(screenshot_b64)
        image_bytes  = base64.b64decode(compressed)
        mime         = "image/jpeg" if image_bytes[:2] == b"\xff\xd8" else "image/png"
        image_part   = Part.from_data(image_bytes, mime_type=mime)
        response     = await _gemini_vision_model.generate_content_async([prompt, image_part])
        return response.text
    except Exception as exc:
        logger.error(f"Gemini vision call failed: {exc}")
        from core.emulated_ai import emulated_vision_response
        return emulated_vision_response(prompt, screenshot_b64)


async def _call_gemini_text(prompt: str) -> str:
    if not _ensure_vertex_init():
        from core.emulated_ai import emulated_text_response
        return emulated_text_response(prompt)
    try:
        response = await _gemini_text_model.generate_content_async(prompt)
        return response.text
    except Exception as exc:
        logger.error(f"Gemini text call failed: {exc}")
        from core.emulated_ai import emulated_text_response
        return emulated_text_response(prompt)


# ── Public API ─────────────────────────────────────────────────────────────


# ── Public API ─────────────────────────────────────────────────────────────

async def analyze_screen(
    screenshot_b64: str,
    task_goal: str,
    current_step: str,
    previous_actions: List[str],
    task_memory_context: str = "",
) -> Dict[str, Any]:
    """Analyze screenshot with full task memory context."""
    prompt = SCREEN_ANALYSIS_PROMPT.format(
        task_goal=task_goal,
        current_step=current_step,
        task_memory=task_memory_context or json.dumps({"task_goal": task_goal, "previous_actions": previous_actions[-5:]}),
    )
    response = await _call_gemini_vision(prompt, screenshot_b64)
    try:
        return _extract_json(response)
    except Exception as exc:
        logger.error(f"Screen analysis parse error: {exc}")
        return {
            "page_description": "Parse error — retrying",
            "ui_elements": [], "task_progress": 0,
            "task_complete": False, "reasoning": str(exc),
            "suggested_next_action": "Wait and retry",
            "current_state": "unknown", "key_observation": "",
            "mock": True,
        }


async def create_task_plan(command: str, context: str = "") -> Dict[str, Any]:
    """Generate step-by-step task plan with expected outcomes and irreversibility flags."""
    prompt = TASK_PLANNING_PROMPT.format(
        command=command,
        context=context or "General web browser",
    )
    response = await _call_gemini_text(prompt)
    try:
        return _extract_json(response)
    except Exception as exc:
        logger.error(f"Task plan parse error: {exc}")
        return {
            "goal": command,
            "steps": [{"step_number": 1, "description": "Analyse the interface",
                       "reasoning": "Initial observation",
                       "expected_outcome": "Page structure understood",
                       "is_irreversible": False}],
            "estimated_steps": 1,
            "risk_factors": [],
            "success_criteria": "Task completed",
            "irreversible_actions": [],
            "mock": True,
        }


async def generate_next_action(
    screenshot_b64: str,
    screen_description: str,
    ui_elements: List[Dict],
    task_goal: str,
    current_step_description: str,
    previous_actions: List[str],
    screen_width: int = 1280,
    screen_height: int = 800,
    cv_regions: Optional[List[Dict]] = None,
    task_memory_context: str = "",
) -> Dict[str, Any]:
    """
    Generate the next action with:
    - Full task memory context
    - Vision grounding (CV + Gemini cross-referenced)
    - Structured explainable JSON (target, reason, grounding_source, is_irreversible)
    """
    # Build grounded element list from CV + Gemini
    grounded = []
    if cv_regions:
        grounded = ground_cv_elements(cv_regions, ui_elements, screen_width, screen_height)

    prompt = ACTION_GENERATION_PROMPT.format(
        task_memory=task_memory_context or json.dumps({
            "task_goal": task_goal,
            "previous_actions": previous_actions[-5:],
        }),
        screen_description=screen_description,
        ui_elements=json.dumps(ui_elements[:10]),
        cv_grounded=json.dumps(grounded[:8]),
        task_goal=task_goal,
        current_step_description=current_step_description,
    )
    response = await _call_gemini_vision(prompt, screenshot_b64)
    try:
        action = _extract_json(response)
        # Convert percentage coords to pixels
        if action.get("x") is not None:
            action["x"] = int(float(action["x"]) / 100 * screen_width)
        if action.get("y") is not None:
            action["y"] = int(float(action["y"]) / 100 * screen_height)
        # Ensure explainability fields always present
        action.setdefault("target", action.get("explanation", "Unknown element")[:60])
        action.setdefault("reason", "Required to advance the task")
        action.setdefault("grounding_source", "gemini")
        action.setdefault("is_irreversible", False)
        return action
    except Exception as exc:
        logger.error(f"Action generation parse error: {exc}")
        return {
            "action_type": "WAIT", "seconds": 2,
            "target": "page",
            "reason": f"Parse error — waiting to recover: {exc}",
            "explanation": f"Waiting due to parse error: {exc}",
            "confidence": 0.5,
            "grounding_source": "none",
            "is_irreversible": False,
            "mock": True,
        }


async def recover_from_error(
    screenshot_b64: str,
    error: str,
    screen_description: str,
    task_goal: str,
    previous_actions: List[str],
    task_memory_context: str = "",
) -> Dict[str, Any]:
    """Generate an error recovery plan with full task memory context."""
    prompt = ERROR_RECOVERY_PROMPT.format(
        error=error,
        screen_description=screen_description,
        task_goal=task_goal,
        task_memory=task_memory_context or json.dumps({
            "task_goal": task_goal,
            "previous_actions": previous_actions[-5:],
        }),
    )
    response = await _call_gemini_vision(prompt, screenshot_b64)
    try:
        result = _extract_json(response)
        # Ensure recovery_action has explainability fields
        ra = result.get("recovery_action", {})
        ra.setdefault("target", "page")
        ra.setdefault("reason", "Recovery after action failure")
        result["recovery_action"] = ra
        return result
    except Exception as exc:
        logger.error(f"Recovery parse error: {exc}")
        return {
            "diagnosis": "Unknown error — waiting before retry",
            "recovery_action": {
                "action_type": "WAIT", "seconds": 2,
                "target": "page",
                "reason": "Waiting to allow page to recover",
                "explanation": "Waiting before retry",
            },
            "alternative_approach": "Restart from beginning",
            "abort_recommended": False,
            "mock": True,
        }

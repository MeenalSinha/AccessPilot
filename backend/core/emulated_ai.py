import base64
import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

def cv_analyse_screenshot(screenshot_b64: str) -> Dict[str, Any]:
    result = {
        "width": 1280, "height": 800,
        "button_count": 0, "input_count": 0,
        "has_table": False, "has_nav": False,
        "dominant_color": "light",
        "edge_density": 0.0,
        "button_positions": [],
        "input_positions":  [],
    }
    try:
        import cv2
        import numpy as np
        raw   = base64.b64decode(screenshot_b64)
        nparr = np.frombuffer(raw, np.uint8)
        img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return result
        h, w = img.shape[:2]
        result["width"]  = w
        result["height"] = h

        gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged   = cv2.Canny(blurred, 30, 100)
        result["edge_density"] = float(np.sum(edged > 0)) / edged.size
        dilated = cv2.dilate(edged, np.ones((3, 3), np.uint8), iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for c in contours:
            area = cv2.contourArea(c)
            if area < 500 or area > 0.3 * w * h:
                continue
            x, y, cw, ch = cv2.boundingRect(c)
            asp = cw / ch if ch > 0 else 0
            cx_pct = round((x + cw / 2) / w * 100, 1)
            cy_pct = round((y + ch / 2) / h * 100, 1)
            w_pct  = round(cw / w * 100, 1)
            h_pct  = round(ch / h * 100, 1)
            if 1.5 < asp < 15 and 20 < ch < 80:
                result["button_positions"].append((cx_pct, cy_pct, w_pct, h_pct))
            if asp > 5 and 25 < ch < 55:
                result["input_positions"].append((cx_pct, cy_pct, w_pct, h_pct))

        result["button_count"] = len(result["button_positions"])
        result["input_count"]  = len(result["input_positions"])
        result["dominant_color"] = "light" if float(np.mean(gray)) > 128 else "dark"
    except Exception as exc:
        logger.debug(f"CV analysis failed: {exc}")
    return result

def emulated_vision_response(prompt: str, screenshot_b64: str) -> str:
    cv = cv_analyse_screenshot(screenshot_b64)
    
    # Action generation
    if "Generate the SINGLE best" in prompt:
        if cv["input_positions"]:
            ix, iy, _, _ = cv["input_positions"][0]
            return json.dumps({
                "action_type": "CLICK", "x": ix, "y": iy,
                "target": "Input field",
                "reason": "Focusing input field for data entry",
                "explanation": "Clicking detected input field",
                "confidence": 0.8, "grounding_source": "cv", "is_irreversible": False
            })
        if cv["button_positions"]:
            bx, by, _, _ = cv["button_positions"][0]
            return json.dumps({
                "action_type": "CLICK", "x": bx, "y": by,
                "target": "Button",
                "reason": "Interacting with primary page button",
                "explanation": "Clicking detected button",
                "confidence": 0.8, "grounding_source": "cv", "is_irreversible": False
            })
        return json.dumps({"action_type": "SCROLL", "direction": "down", "target": "page", "reason": "No elements found"})

    # Screen analysis
    ui_elements = []
    for etype, positions in [("input", cv["input_positions"]), ("button", cv["button_positions"])]:
        for i, (cx, cy, wp, hp) in enumerate(positions[:5]):
            ui_elements.append({
                "element_type": etype, "label": f"{etype.capitalize()} {i+1}",
                "x": cx, "y": cy, "width": wp, "height": hp,
                "confidence": 0.7, "interactable": True
            })

    return json.dumps({
        "page_description": f"Emulated view of page with {cv['button_count']} buttons",
        "current_state": "Ready",
        "ui_elements": ui_elements,
        "task_progress": 0.5,
        "task_complete": False,
        "reasoning": "Emulated reasoning based on CV detection",
        "suggested_next_action": "Click the first button",
        "key_observation": "Page loaded in emulated mode"
    })

def emulated_text_response(prompt: str) -> str:
    return json.dumps({
        "goal": "Emulated Task",
        "steps": [
            {"step_number": 1, "description": "Navigate to URL", "reasoning": "Start task", "expected_outcome": "Loaded"},
            {"step_number": 2, "description": "Execute action", "reasoning": "Advance task", "expected_outcome": "Finished"}
        ],
        "estimated_steps": 2, "risk_factors": [], "success_criteria": "Done", "irreversible_actions": []
    })

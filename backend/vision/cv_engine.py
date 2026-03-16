"""
Computer Vision Module
OpenCV-based UI element detection to augment Gemini's visual analysis.
Detects buttons, inputs, and interactive regions from screenshots.
"""
import base64
import logging
from typing import Dict, List, Optional, Tuple
import io

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False
    logger.warning("OpenCV not available. Computer vision augmentation disabled.")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def b64_to_numpy(screenshot_b64: str) -> Optional[any]:
    """Convert base64 PNG to numpy array."""
    if not CV_AVAILABLE:
        return None
    try:
        img_bytes = base64.b64decode(screenshot_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        logger.error(f"b64_to_numpy failed: {e}")
        return None


def detect_interactive_regions(screenshot_b64: str) -> List[Dict]:
    """
    Detect clickable/interactive UI regions using computer vision.
    Returns list of detected regions with bounding boxes.
    """
    if not CV_AVAILABLE:
        return []

    img = b64_to_numpy(screenshot_b64)
    if img is None:
        return []

    height, width = img.shape[:2]
    regions = []

    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # --- Detect rounded rectangles (buttons) ---
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 30, 100)
        dilated = cv2.dilate(edged, np.ones((3, 3), np.uint8), iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 500 or area > 0.3 * width * height:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            aspect = w / h if h > 0 else 0
            # Button-like: wide, not too tall
            if 1.5 < aspect < 15 and 20 < h < 80:
                regions.append({
                    "element_type": "button_candidate",
                    "x": round((x + w / 2) / width * 100, 1),
                    "y": round((y + h / 2) / height * 100, 1),
                    "width": round(w / width * 100, 1),
                    "height": round(h / height * 100, 1),
                    "confidence": 0.6,
                    "bbox": [x, y, w, h],
                })

        # --- Detect text input fields ---
        # Look for thin horizontal rectangles (input fields)
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 1000 or area > 0.15 * width * height:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            aspect = w / h if h > 0 else 0
            if aspect > 5 and 25 < h < 55:
                regions.append({
                    "element_type": "input_candidate",
                    "x": round((x + w / 2) / width * 100, 1),
                    "y": round((y + h / 2) / height * 100, 1),
                    "width": round(w / width * 100, 1),
                    "height": round(h / height * 100, 1),
                    "confidence": 0.65,
                    "bbox": [x, y, w, h],
                })

        # --- Detect color-prominent regions (likely buttons/CTAs) ---
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # Blue range (common button color)
        blue_mask = cv2.inRange(hsv, np.array([100, 100, 100]), np.array([130, 255, 255]))
        # Green range
        green_mask = cv2.inRange(hsv, np.array([40, 100, 100]), np.array([80, 255, 255]))
        color_mask = cv2.bitwise_or(blue_mask, green_mask)
        color_contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in color_contours:
            area = cv2.contourArea(contour)
            if area < 800 or area > 0.1 * width * height:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            regions.append({
                "element_type": "colored_button",
                "x": round((x + w / 2) / width * 100, 1),
                "y": round((y + h / 2) / height * 100, 1),
                "width": round(w / width * 100, 1),
                "height": round(h / height * 100, 1),
                "confidence": 0.75,
                "bbox": [x, y, w, h],
            })

        # Deduplicate overlapping regions
        regions = _deduplicate_regions(regions)
        logger.debug(f"CV detected {len(regions)} regions")
        return regions[:20]  # limit to top 20

    except Exception as e:
        logger.error(f"CV detection error: {e}")
        return []


def _deduplicate_regions(regions: List[Dict], iou_threshold: float = 0.5) -> List[Dict]:
    """Remove highly overlapping detected regions."""
    if not regions:
        return regions

    def iou(a, b):
        # Using percentage coordinates
        ax1, ay1 = a["x"] - a["width"] / 2, a["y"] - a["height"] / 2
        ax2, ay2 = a["x"] + a["width"] / 2, a["y"] + a["height"] / 2
        bx1, by1 = b["x"] - b["width"] / 2, b["y"] - b["height"] / 2
        bx2, by2 = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        inter_w = max(0, min(ax2, bx2) - max(ax1, bx1))
        inter_h = max(0, min(ay2, by2) - max(ay1, by1))
        inter = inter_w * inter_h
        union = a["width"] * a["height"] + b["width"] * b["height"] - inter
        return inter / union if union > 0 else 0

    kept = []
    for region in sorted(regions, key=lambda r: -r["confidence"]):
        overlaps = any(iou(region, k) > iou_threshold for k in kept)
        if not overlaps:
            kept.append(region)
    return kept


def annotate_screenshot(screenshot_b64: str, ui_elements: List[Dict]) -> Optional[str]:
    """
    Draw bounding boxes on screenshot for visualization.
    Returns annotated screenshot as base64.
    """
    if not CV_AVAILABLE:
        return screenshot_b64

    img = b64_to_numpy(screenshot_b64)
    if img is None:
        return screenshot_b64

    height, width = img.shape[:2]

    color_map = {
        "button": (52, 152, 219),      # Blue
        "input": (46, 204, 113),        # Green
        "link": (231, 76, 60),          # Red
        "menu": (155, 89, 182),         # Purple
        "table": (241, 196, 15),        # Yellow
        "icon": (26, 188, 156),         # Teal
        "text": (149, 165, 166),        # Gray
        "dropdown": (230, 126, 34),     # Orange
    }

    try:
        for element in ui_elements:
            x_pct = element.get("x", 50)
            y_pct = element.get("y", 50)
            w_pct = element.get("width", 10)
            h_pct = element.get("height", 5)
            etype = element.get("element_type", "text").lower()

            cx = int(x_pct / 100 * width)
            cy = int(y_pct / 100 * height)
            w = int(w_pct / 100 * width)
            h = int(h_pct / 100 * height)
            x1, y1 = cx - w // 2, cy - h // 2
            x2, y2 = cx + w // 2, cy + h // 2

            color = color_map.get(etype, (200, 200, 200))
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

            label = element.get("label", etype)[:20]
            font_scale = 0.4
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
            cv2.rectangle(img, (x1, y1 - lh - 4), (x1 + lw + 4, y1), color, -1)
            cv2.putText(img, label, (x1 + 2, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1)

        _, buffer = cv2.imencode(".png", img)
        return base64.b64encode(buffer).decode("utf-8")

    except Exception as e:
        logger.error(f"Annotation error: {e}")
        return screenshot_b64


def calculate_click_confidence(
    target_element: Dict,
    screenshot_b64: str,
    x: int,
    y: int,
) -> float:
    """
    Calculate confidence that a click at (x, y) will hit the target element.
    Uses CV to verify the region is interactable.
    """
    if not CV_AVAILABLE:
        return 0.8

    img = b64_to_numpy(screenshot_b64)
    if img is None:
        return 0.8

    height, width = img.shape[:2]
    if x < 0 or x >= width or y < 0 or y >= height:
        return 0.0

    # Check if there's an edge/border near the click point (suggests UI element)
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        region = gray[
            max(0, y - 20):min(height, y + 20),
            max(0, x - 40):min(width, x + 40)
        ]
        edges = cv2.Canny(region, 30, 100)
        edge_density = np.sum(edges > 0) / edges.size if edges.size > 0 else 0
        # Higher edge density = more likely to be a UI element
        confidence = min(0.95, 0.5 + edge_density * 3)
        return round(confidence, 2)
    except Exception:
        return 0.8

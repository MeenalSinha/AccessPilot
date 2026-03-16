"""
Automation Engine — Playwright-based browser control
Executes AI-generated actions on real browser instances.

FIX: NAVIGATE/CLICK/TYPE/HOVER now return explicit failure when no page available
     instead of silently returning None (implicit None = unhandled in agent loop).
FIX: TYPE validates non-empty text before executing.
FIX: All action branches have explicit return values.
FIX: BrowserSession.stop() properly handles already-stopped state.
FIX: Screenshot compressed to reduce WebSocket payload size.
"""
import asyncio
import base64
import logging
from io import BytesIO
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed — using mock automation engine.")


def _compress_screenshot_bytes(png_bytes: bytes, quality: int = 80) -> str:
    """Compress screenshot PNG to JPEG and return as base64."""
    try:
        from PIL import Image
        img = Image.open(BytesIO(png_bytes)).convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return base64.b64encode(png_bytes).decode("utf-8")


class BrowserSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.playwright = None
        self.browser: Optional[Any] = None
        self.context: Optional[Any] = None
        self.page: Optional[Any] = None
        self.is_running = False
        self.viewport_width = 1280
        self.viewport_height = 800

    async def start(self, headless: bool = True) -> bool:
        if not PLAYWRIGHT_AVAILABLE:
            logger.info(f"Mock browser started for {self.session_id}")
            self.is_running = True
            return True
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            self.context = await self.browser.new_context(
                viewport={"width": self.viewport_width, "height": self.viewport_height},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self.page = await self.context.new_page()
            self.is_running = True
            logger.info(f"Browser started for session {self.session_id}")
            return True
        except Exception as e:
            logger.error(f"Browser start failed: {e}")
            # Still mark as running so agent loop can use mock mode
            self.is_running = True
            return False

    async def stop(self):
        self.is_running = False
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        try:
            if self.browser and PLAYWRIGHT_AVAILABLE:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright and PLAYWRIGHT_AVAILABLE:
                await self.playwright.stop()
        except Exception:
            pass
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    async def take_screenshot(self) -> str:
        """Capture current screen as base64 JPEG (compressed)."""
        if not PLAYWRIGHT_AVAILABLE or not self.page:
            return _generate_mock_screenshot()
        try:
            png_bytes = await self.page.screenshot(type="png", full_page=False)
            return _compress_screenshot_bytes(png_bytes)
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return _generate_mock_screenshot()

    async def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single action and return result dict with success flag."""
        action_type = action.get("action_type", "").upper()

        # Guard: page must exist for browser actions
        page_required = action_type in {"NAVIGATE", "CLICK", "TYPE", "SCROLL", "PRESS", "HOVER", "SELECT", "CLEAR"}
        if page_required and not self.page and PLAYWRIGHT_AVAILABLE:
            return {"success": False, "message": "Browser page not initialised"}

        try:
            if action_type == "NAVIGATE":
                url = action.get("url", "").strip()
                if not url:
                    return {"success": False, "message": "NAVIGATE: no url provided"}
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                if self.page:
                    await self.page.goto(url, wait_until="domcontentloaded", timeout=20000)
                return {"success": True, "message": f"Navigated to {url}"}

            elif action_type == "CLICK":
                x, y = action.get("x"), action.get("y")
                if x is None or y is None:
                    return {"success": False, "message": "CLICK: missing x or y coordinates"}
                if self.page:
                    await self.page.mouse.click(float(x), float(y))
                return {"success": True, "message": f"Clicked at ({x}, {y})"}

            elif action_type == "TYPE":
                text = action.get("text") or ""
                if not text:
                    return {"success": False, "message": "TYPE: no text provided"}
                if self.page:
                    await self.page.keyboard.type(str(text), delay=40)
                return {"success": True, "message": f"Typed: {str(text)[:60]}"}

            elif action_type == "SCROLL":
                direction = action.get("direction", "down").lower()
                amount = int(action.get("amount", 400))
                if direction == "down":
                    dx, dy = 0, amount
                elif direction == "up":
                    dx, dy = 0, -amount
                elif direction == "right":
                    dx, dy = amount, 0
                else:  # left
                    dx, dy = -amount, 0
                if self.page:
                    await self.page.mouse.wheel(dx, dy)
                return {"success": True, "message": f"Scrolled {direction} by {amount}px"}

            elif action_type == "PRESS":
                key = action.get("key", "Enter")
                if not key:
                    return {"success": False, "message": "PRESS: no key provided"}
                if self.page:
                    await self.page.keyboard.press(str(key))
                return {"success": True, "message": f"Pressed {key}"}

            elif action_type == "WAIT":
                seconds = float(action.get("seconds") or 1.0)
                seconds = min(seconds, 30.0)  # cap at 30s
                await asyncio.sleep(seconds)
                return {"success": True, "message": f"Waited {seconds:.1f}s"}

            elif action_type == "HOVER":
                x, y = action.get("x"), action.get("y")
                if x is None or y is None:
                    return {"success": False, "message": "HOVER: missing x or y coordinates"}
                if self.page:
                    await self.page.mouse.move(float(x), float(y))
                return {"success": True, "message": f"Hovered at ({x}, {y})"}

            elif action_type == "SELECT":
                x, y = action.get("x"), action.get("y")
                text = action.get("text") or ""
                if x is None or y is None:
                    return {"success": False, "message": "SELECT: missing coordinates"}
                if self.page:
                    await self.page.mouse.click(float(x), float(y))
                    await asyncio.sleep(0.3)
                    if text:
                        await self.page.keyboard.type(str(text), delay=40)
                return {"success": True, "message": f"Selected: {str(text)[:40]}"}

            elif action_type == "CLEAR":
                x, y = action.get("x"), action.get("y")
                if x is None or y is None:
                    return {"success": False, "message": "CLEAR: missing coordinates"}
                if self.page:
                    await self.page.mouse.click(float(x), float(y))
                    await self.page.keyboard.press("Control+a")
                    await self.page.keyboard.press("Delete")
                return {"success": True, "message": "Cleared input field"}

            else:
                return {"success": False, "message": f"Unknown action type: {action_type}"}

        except Exception as e:
            logger.error(f"Action execution error ({action_type}): {e}")
            return {"success": False, "message": str(e), "error": str(e)}

    async def get_page_url(self) -> str:
        if self.page:
            try:
                return self.page.url
            except Exception:
                pass
        return ""

    async def get_page_title(self) -> str:
        if self.page:
            try:
                return await self.page.title()
            except Exception:
                pass
        return ""


def _generate_mock_screenshot() -> str:
    """Return a minimal valid white PNG as base64 (used when no real browser)."""
    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


class AutomationEngine:
    """High-level singleton managing all BrowserSession instances."""

    def __init__(self):
        self._sessions: Dict[str, BrowserSession] = {}

    async def create_session(self, session_id: str, headless: bool = True) -> BrowserSession:
        # Stop existing session for this id first (prevent leaks)
        await self.stop_session(session_id)
        session = BrowserSession(session_id)
        await session.start(headless=headless)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        return self._sessions.get(session_id)

    async def stop_session(self, session_id: str):
        session = self._sessions.pop(session_id, None)
        if session:
            await session.stop()

    async def cleanup_all(self):
        for sid in list(self._sessions.keys()):
            await self.stop_session(sid)


# Module-level singleton
engine = AutomationEngine()

"""
Shared application state singletons.

Both main.py and api/routes.py import from here — no circular dependency.
main.py lifespan also attaches these to app.state for backward compatibility.
"""
from core.session_manager import SessionManager
from core.websocket_manager import WebSocketManager

session_manager = SessionManager()
ws_manager = WebSocketManager()

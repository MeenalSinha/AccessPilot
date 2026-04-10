"""
AccessPilot Backend — FastAPI entry point.

Singletons live in core.state (imported by both here and api/routes.py).
Lifespan attaches them to app.state for any third-party middleware that
may want to introspect the app, but routes no longer depend on app.state.
"""
import json
import logging
import os
import signal
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Import shared singletons — same objects routes.py uses
from core.state import session_manager, ws_manager
from engine.automation import engine as automation_engine
from api.routes import router as api_router
from core.database import init_db


def _handle_sigterm(*_):
    logger.info("SIGTERM received — initiating graceful shutdown")


signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT,  _handle_sigterm)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AccessPilot starting (version=1.1.0)")
    # Attach to app.state for middleware / diagnostic introspection
    app.state.session_manager = session_manager
    app.state.ws_manager = ws_manager
    
    # Initialize real database
    await init_db()
    
    yield
    logger.info("Shutting down — cleaning up sessions and browsers")
    await session_manager.cleanup_all()
    await automation_engine.cleanup_all()
    logger.info("Shutdown complete")


app = FastAPI(
    title="AccessPilot API",
    description="Universal UI Agent — visual browser automation powered by Gemini",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=500)

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_API_KEY = os.environ.get("API_KEY", "")


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """Attach X-Request-ID; enforce API key on /api/* when configured."""
    request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
    if _API_KEY and request.url.path.startswith("/api/"):
        if request.headers.get("x-api-key", "") != _API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
                headers={"x-request-id": request_id},
            )
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check():
    """Deep health check — Vertex AI status, production readiness."""
    from core.gemini_client import _ensure_vertex_init
    vertex_ok = _ensure_vertex_init()
    return {
        "status": "healthy" if vertex_ok else "degraded",
        "version": "1.1.0",
        "production_ready": vertex_ok,
        "vertex_ai": "configured" if vertex_ok else "missing_project_id",
        "browser_engine": "playwright",
        "auth_enabled": bool(_API_KEY),
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: Optional[str] = None):
    safe_id = _sanitise_session_id(session_id)
    if not safe_id:
        await websocket.close(code=1008)
        return
    
    # Enforce API key on WS if configured
    if _API_KEY and token != _API_KEY:
        logger.warning(f"Unauthorized WS connection attempt for {safe_id}")
        await websocket.close(code=1008)
        return

    await ws_manager.connect(safe_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                logger.warning(f"Malformed WS message from {safe_id}")
                continue
            await ws_manager.handle_message(safe_id, msg, session_manager)
    except WebSocketDisconnect:
        await ws_manager.disconnect(safe_id)
    except Exception as e:
        logger.error(f"WebSocket error for {safe_id}: {e}")
        await ws_manager.disconnect(safe_id)


def _sanitise_session_id(session_id: str) -> str:
    import re
    if not session_id:
        return ""
    if not re.match(r"^[a-zA-Z0-9\-_]{1,64}$", session_id):
        logger.warning(f"Rejected unsafe session_id: {session_id!r}")
        return ""
    return session_id


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=os.environ.get("RELOAD", "false").lower() == "true",
        log_config=None,
    )

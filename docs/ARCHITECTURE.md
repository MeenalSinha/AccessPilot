# AccessPilot — System Architecture

## Full Pipeline

```mermaid
flowchart TD
    U([User]) -->|Natural language command| FE[React Frontend\nPort 3000]
    U -->|Voice input| FE

    FE -->|POST /api/v1/command| BE[FastAPI Backend\nPort 8000]
    BE <-->|WebSocket /ws/:sessionId| FE

    BE --> ORCH[Agent Orchestrator\ncore/agent.py]

    ORCH --> PLAN[Task Planner\nGemini Text API]
    PLAN -->|Structured step list| ORCH

    ORCH --> AUTO[Automation Engine\nPlaywright Browser]
    AUTO -->|PNG screenshot| ORCH

    ORCH --> GEM[Gemini Vision\nVertex AI]
    GEM -->|UI element analysis\nNext action JSON| ORCH

    ORCH --> CV[CV Engine\nOpenCV]
    CV -->|Augmented element coords| ORCH

    ORCH -->|Execute action| AUTO
    AUTO -->|CLICK / TYPE / SCROLL\nPRESS / WAIT / NAVIGATE| WEB[Target Website]
    WEB -->|New page state| AUTO

    ORCH -->|Events via WebSocket| FE
    FE --> SCREEN[Screen Viewer]
    FE --> ALOG[Action Log]
    FE --> PANEL[Analysis Panel]
    FE --> TPLAN[Task Plan Panel]
```

## Component Responsibilities

| Component | File | Role |
|-----------|------|------|
| React Frontend | `frontend/src/` | UI, command input, live screen, action log |
| FastAPI Backend | `backend/main.py` | REST API, WebSocket hub, session management |
| Agent Orchestrator | `core/agent.py` | Main feedback loop, coordinates all subsystems |
| Gemini Client | `core/gemini_client.py` | Vision analysis, task planning, action generation |
| Automation Engine | `engine/automation.py` | Playwright browser control, screenshot capture |
| CV Engine | `vision/cv_engine.py` | OpenCV button/input detection, annotation |
| Session Manager | `core/session_manager.py` | Per-session state and lifecycle |
| WebSocket Manager | `core/websocket_manager.py` | Real-time event broadcasting to frontend |

## Data Flow Per Step

```
1. Screenshot captured        (Playwright → PNG → base64)
2. CV pre-processing          (OpenCV → candidate element regions)
3. Gemini vision analysis     (Vertex AI → structured JSON)
4. Action decision            (Gemini → CLICK/TYPE/SCROLL/etc.)
5. Action execution           (Playwright → browser interaction)
6. Event broadcast            (WebSocket → frontend panels update)
7. Repeat until task complete or max steps reached
```

## Cloud Deployment

```
Firebase Hosting  ──→  React SPA (CDN)
        │
        ▼
Cloud Run  ──→  FastAPI Backend (containerised)
        │
        ▼
Vertex AI  ──→  Gemini 1.5 Pro Vision
        │
        ▼
Cloud Storage  ──→  Screenshot archive (optional)
```

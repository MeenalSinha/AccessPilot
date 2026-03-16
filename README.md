# AccessPilot — Universal UI Agent

An AI agent that becomes the user's hands on screen. AccessPilot observes
screenshots, understands intent, plans actions, and controls any software
interface visually — no APIs or DOM access required.

```
User command → Screenshot → Gemini Vision → Action plan → Browser control → Repeat
```

---

## Features

- **Visual UI understanding** — Gemini multimodal analyses screenshots; detects buttons, inputs, forms, menus, tables, links
- **Natural language + voice commands** — text or Web Speech API input converted into structured task plans
- **Multi-step task planning** — Gemini generates step-by-step plans with expected outcomes and irreversibility flags
- **Autonomous browser control** — Playwright executes CLICK, TYPE, SCROLL, PRESS, WAIT, NAVIGATE, HOVER, SELECT, CLEAR
- **Computer vision augmentation** — OpenCV detects interactive regions; cross-referenced with Gemini by IoU (Vision Grounding)
- **Task Memory** — structured long-term context (completed steps, observations, grounding hits) injected into every Gemini prompt
- **Strict action schema** — `ValidatedAction.from_raw()` rejects malformed Gemini responses before any browser action
- **Confidence threshold** — actions with confidence < 70% pause and ask the user before executing
- **Self-healing navigation** — when elements aren't found: scroll → text-similarity search → ask user, with human-readable messages
- **Explainable actions** — every action shows target element, reason, confidence bar, grounding source (CV/Gemini/Combined)
- **Reasoning Trail panel** — Explainable AI Mode: live step-by-step narrative with success/failure indicators
- **Action confirmation dialog** — irreversible actions (payment, delete, send) show a countdown modal
- **Error recovery** — 3 self-healing strategies then Gemini deep recovery with full screenshot re-analysis
- **Real-time feedback loop** — every action triggers a new screenshot, CV scan, and Gemini re-analysis
- **Demo Mode** — works without GCP; CV-assisted mock analyses real screenshots so responses reflect actual page content

---

## Quick Start

Three paths — pick the one that fits your setup.

| Path | GCP needed? | Time | Best for |
|---|---|---|---|
| **[A] Demo Mode** (no GCP) | ✗ | ~2 min | Judges wanting to run it right now |
| **[B] Full local** (with GCP) | ✓ | ~5 min | Evaluating live Gemini AI |
| **[C] Docker** | ✓ | ~5 min | Clean reproducible environment |

---

### Path A — Demo Mode (no Google Cloud account required)

The agent runs with real Playwright browser automation and real OpenCV computer vision.
Gemini responses are mocked using actual CV analysis of live screenshots — elements and
positions reflect the real page, not hardcoded values. A yellow banner in the UI makes
this transparent.

**Prerequisites:** Python 3.11+, Node.js 18+

```bash
# 1. Clone
git clone https://github.com/your-org/accesspilot.git
cd accesspilot

# 2. Backend — install deps and launch
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium --with-deps
uvicorn main:app --port 8000

# 3. Frontend — new terminal
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** — the yellow "Demo Mode" banner confirms Playwright and
OpenCV are running. Click any scenario card to watch the agent operate a real browser.

**Verify it's working:**
```
GET http://localhost:8000/health
→ {"status":"ok","vertex_available":false,"running_sessions":0}
```

---

### Path B — Full local with live Gemini

**Prerequisites:** Python 3.11+, Node.js 18+, GCP project with Vertex AI API enabled,
service account key with `roles/aiplatform.user`.

#### Step 1 — GCP service account key

```bash
# Create a service account and download a key
gcloud iam service-accounts create accesspilot-sa \
  --display-name "AccessPilot Service Account"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member "serviceAccount:accesspilot-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role "roles/aiplatform.user"

gcloud iam service-accounts keys create backend/gcp-key.json \
  --iam-account accesspilot-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

#### Step 2 — Configure environment

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env`:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./gcp-key.json
API_KEY=                        # leave blank for local dev
ALLOWED_ORIGINS=*
```

#### Step 3 — Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium --with-deps
uvicorn main:app --reload --port 8000
```

**Expected startup output:**
```
INFO:     AccessPilot starting (version=1.0.0)
INFO:     Vertex AI ready — project=your-project-id location=us-central1
INFO:     Uvicorn running on http://0.0.0.0:8000
```

#### Step 4 — Frontend

```bash
cd frontend
npm install
npm run dev
```

**Verify live Gemini is connected:**
```
GET http://localhost:8000/health
→ {"status":"ok","vertex_available":true,"vertex_project":"your-project-id"}
```

The Demo Mode banner will not appear — the UI shows full AI reasoning.

---

### Path C — Docker Compose

```bash
# 1. Place your GCP key in backend/
cp ~/your-gcp-key.json backend/gcp-key.json

# 2. Set your project ID
export GOOGLE_CLOUD_PROJECT=your-project-id

# 3. Build and start (first build ~3 min, subsequent ~30 sec)
docker-compose up --build
```

Services:
- Frontend: **http://localhost:3000**
- Backend API: **http://localhost:8000**
- Swagger docs: **http://localhost:8000/docs**

**Health check** (runs automatically every 15 s):
```bash
curl http://localhost:8000/health
```

**Stop:**
```bash
docker-compose down
```

---

### Running the test suite

No server required — all 189 tests run directly against the modules:

```bash
cd backend
source venv/bin/activate
pip install pytest pytest-asyncio
python -m pytest test_integration.py --asyncio-mode=auto -v
```

**Expected result:**
```
189 passed in ~35s
```

Tests cover: prompt templates, JSON extraction, CV-assisted mock, schema validation
(ValidatedAction), confidence threshold, TaskMemory, vision grounding, self-healing engine,
WebSocket handlers, all HTTP endpoints via TestClient, end-to-end Playwright pipeline,
and all frontend component files.

---

### Deploy to Google Cloud (production)

```bash
# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  aiplatform.googleapis.com \
  cloudbuild.googleapis.com \
  firebase.googleapis.com

# Deploy backend to Cloud Run
cd backend
gcloud run deploy accesspilot-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --set-env-vars GOOGLE_CLOUD_PROJECT=$(gcloud config get project)
# Note the deployed URL: https://accesspilot-backend-xxx-uc.a.run.app

# Deploy frontend to Firebase Hosting
npm install -g firebase-tools
firebase login
cd frontend
echo "VITE_API_URL=https://your-cloud-run-url"  >  .env
echo "VITE_WS_URL=wss://your-cloud-run-url"     >> .env
npm run build
cd ..
firebase deploy --only hosting
```

Or use the automated Cloud Build pipeline:
```bash
gcloud builds submit --config cloudbuild.yaml
```



## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/command` | Start an agent task |
| `POST` | `/api/v1/stop` | Stop a running session |
| `GET` | `/api/v1/sessions` | List all sessions |
| `GET` | `/api/v1/session/:id` | Get session details |
| `GET` | `/api/v1/session/:id/screenshot` | Get latest screenshot |
| `POST` | `/api/v1/analyze` | Analyze a screenshot (no agent loop) |
| `GET` | `/api/v1/demo-scenarios` | Get pre-built demo scenarios |
| `WS` | `/ws/:sessionId` | Real-time agent event stream |

### POST /api/v1/command

```json
{
  "command": "Find the cheapest flight from Delhi to Mumbai tomorrow",
  "session_id": "optional-uuid",
  "target_url": "https://www.google.com/travel/flights",
  "context": {}
}
```

### WebSocket events (server → client)

| Event type | Description |
|------------|-------------|
| `connected` | WebSocket handshake complete |
| `status` | Agent state change: `planning` → `running` → `completed` / `error` |
| `plan` | Task plan generated — steps, success_criteria, irreversible_actions |
| `screenshot` | Annotated JPEG screenshot after every action |
| `analysis` | Gemini screen analysis + CV region count + memory_summary |
| `action` | Full explainable action: type, target, reason, confidence, grounding_source |
| `confirm_required` | Agent paused for low-confidence (&lt;70%) or irreversible action |
| `healing_failed` | Self-healing exhausted — user guidance requested |
| `log` | Step log entry with level (info/warning/error/success) |
| `error` | Agent error broadcast |
| `pong` | Heartbeat response |

### WebSocket commands (client → server)

```json
{ "type": "ping" }
{ "type": "stop" }
{ "type": "confirm", "approved": true }
```

---

## Demo Scenarios

Three core demos show the full capability of AccessPilot's visual agent.
Run them from the **Scenarios** tab in the UI — no setup required.

---

### Demo 1 — Flight Booking (Web Navigation)

**Command:** `Find the cheapest flight from Delhi to Mumbai tomorrow`

**What the agent does:**

```
Step 01: NAVIGATE  → Opens flight search website
         Target: Browser address bar
         Reason: Must load the correct URL before interacting

Step 02: CLICK     → Focuses the "From" city input field
         Target: Origin input field  [CV+Gemini: 94% confidence]
         Reason: Required to enter departure city

Step 03: TYPE      → Types "Delhi"
         Target: Origin input field
         Reason: Enter departure city as specified in command

Step 04: CLICK     → Focuses the "To" city input field
         Target: Destination input field  [CV+Gemini: 91% confidence]
         Reason: Required to enter destination city

Step 05: TYPE      → Types "Mumbai"
         Target: Destination input field
         Reason: Enter destination as specified in command

Step 06: CLICK     → Clicks "Search Flights" button
         Target: Search button  [OpenCV grounded: 88% confidence]
         Reason: Submit the search to retrieve flight results
```

**Expected output:** Table of flights sorted by price with cheapest highlighted in green.

---

### Demo 2 — Form Automation (Form Filling)

**Command:** `Fill this registration form with my details`

**What the agent does:**

```
Step 01: NAVIGATE  → Opens the registration form URL
         Target: Browser
         Reason: Load the target page

Step 02: CLICK     → Focuses first input field
         Target: Full Name input  [Gemini: 93% confidence]
         Reason: Begin sequential form fill

Step 03: TYPE      → Enters name
         Target: Full Name input
         Reason: Populate required name field

Step 04: CLICK     → Focuses email field
         Target: Email input  [CV+Gemini: 89% confidence]
         Reason: Move to next form field

Step 05: TYPE      → Enters email address
         Target: Email input
         Reason: Populate required email field
```

**Expected output:** All form fields filled. Agent identifies field labels via
Gemini vision, maps them to profile data, fills each in order, then submits.

---

### Demo 3 — Dashboard Automation (Invoice Download)

**Command:** `Download all invoices from last month`

**What the agent does:**

```
Step 01: NAVIGATE  → Opens dashboard URL
         Target: Browser
         Reason: Load the billing dashboard

Step 02: CLICK     → Opens date filter panel
         Target: Filter / Date Range button  [OpenCV: 82% confidence]
         Reason: Must apply date filter before downloading

Step 03: CLICK     → Selects "Last Month" preset
         Target: Last Month option in date picker  [Gemini: 87% confidence]
         Reason: Narrow results to the requested time period

Step 04: CLICK     → Applies the filter
         Target: Apply button  [CV+Gemini: 91% confidence]
         Reason: Confirm filter selection to update table

Step 05: CLICK     → Clicks Download All button
         Target: Download button  [Gemini: 85% confidence]
         Reason: Initiate file download of filtered invoices

Step 06: WAIT      → Waits for download to complete
         Target: Page
         Reason: Allow time for files to save

Step 07: VERIFY    → Confirms download success message
         Target: Status notification
         Reason: Validate task completion
```

**Expected output:** All invoices from last month downloaded as files.
Agent explains each step in the Reasoning Trail panel in real time.

---

### What Judges See in the UI

| Panel | What it shows |
|---|---|
| **Screen Capture** | Live annotated screenshot — OpenCV bounding boxes + Gemini labels |
| **Reasoning Trail** | Step-by-step: `CLICK → "Search button" → Required to submit search → 92%` |
| **Action Log** | Every action with target, reason, confidence bar, grounding source |
| **Analysis** | UI elements detected, CV region count, task progress % |
| **Task Plan** | Full step list with current step highlighted |

---

## Project Structure

```
accesspilot/
├── backend/
│   ├── main.py                    # FastAPI app, WebSocket endpoint, health check
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── test_integration.py        # 189 tests — no server required
│   ├── api/
│   │   └── routes.py              # All REST endpoints + /demo/run
│   ├── core/
│   │   ├── agent.py               # Feedback loop, ValidatedAction, self-healing wiring
│   │   ├── gemini_client.py       # Vertex AI / Gemini — vision + text + CV mock
│   │   ├── memory.py              # TaskMemory — long-term task context
│   │   ├── models.py              # Pydantic models, ValidatedAction schema
│   │   ├── self_healing.py        # 3-strategy recovery engine
│   │   ├── session_manager.py     # Session lifecycle, TTL eviction
│   │   ├── state.py               # Shared singletons (no circular imports)
│   │   └── websocket_manager.py   # Real-time event broadcasting
│   ├── engine/
│   │   └── automation.py          # Playwright browser control, 9 actions
│   ├── vision/
│   │   └── cv_engine.py           # OpenCV button/input detection, annotation
│   └── prompts/
│       └── templates.py           # Gemini prompt templates
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                # Root component, 3-column layout, confirm wiring
│       ├── components/
│       │   ├── ActionLog.jsx      # Live event feed using ExplainableAction cards
│       │   ├── AnalysisPanel.jsx  # CV region breakdown
│       │   ├── CommandInput.jsx   # Text + voice input, localStorage history
│       │   ├── ConfirmDialog.jsx  # Countdown modal for low-conf + irreversible actions
│       │   ├── DemoBanner.jsx     # Demo Mode indicator with component status chips
│       │   ├── DemoScenarios.jsx  # Pre-built scenario cards
│       │   ├── ExplainableAction.jsx # Structured action card: target, reason, confidence
│       │   ├── Header.jsx         # Status bar, connection indicator
│       │   ├── ReasoningTrail.jsx # Explainable AI Mode step-by-step panel
│       │   ├── ScreenViewer.jsx   # Live annotated screenshot
│       │   ├── StatusBar.jsx      # Agent status strip
│       │   └── TaskPlanPanel.jsx  # Step list with progress bar
│       ├── hooks/
│       │   ├── useAgentSocket.js  # WebSocket with exponential backoff reconnect
│       │   └── useVoiceInput.js   # Web Speech API hook
│       └── utils/
│           ├── api.js             # Backend API client
│           └── uuid.js            # UUID helper
├── docs/
│   ├── ARCHITECTURE.md            # Component table
│   └── architecture-diagram.html  # Interactive system diagram (open in browser)
├── docker-compose.yml             # Resource limits, healthcheck
├── cloudbuild.yaml                # GCP CI/CD — build + Cloud Run + Firebase
└── firebase.json                  # Firebase Hosting config
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Yes | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | No | Vertex AI region (default: `us-central1`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes | Path to GCP service account key JSON |

### Frontend (`frontend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | Backend REST URL |
| `VITE_WS_URL` | `ws://localhost:8000` | Backend WebSocket URL |

---

## Running Tests

```bash
cd backend
source venv/bin/activate
python -m pytest test_integration.py --asyncio-mode=auto -v
```

**Expected:** `189 passed` — no server required. Tests cover prompts, schema validation,
TaskMemory, self-healing, vision grounding, all HTTP endpoints, and a full Playwright
end-to-end pipeline against a real browser.

---

## How It Works

1. **User submits a command** (text or voice) in the React frontend
2. **Frontend calls** `POST /api/v1/command` and opens a WebSocket connection
3. **Backend creates a session**, initialises TaskMemory and SelfHealingEngine, launches headless Chromium
4. **Gemini generates a task plan** — structured steps with expected outcomes and irreversibility flags
5. **Agent loop begins** (up to 30 steps, 10 min timeout):
   - Playwright captures a PNG screenshot → JPEG compressed
   - OpenCV detects interactive regions (buttons, inputs, colored CTAs)
   - Gemini Vision analyses the screenshot with full TaskMemory context injected
   - Vision Grounding cross-references CV regions with Gemini elements by IoU
   - Gemini generates the next action: type, target, reason, confidence, grounding_source
   - `ValidatedAction.from_raw()` enforces strict schema — malformed responses rejected
   - If confidence < 0.70 or action is irreversible → pause and send `confirm_required` to UI
   - Playwright executes the validated action in the browser
   - TaskMemory updated: step record, observation, grounding hits
   - All events broadcast to frontend via WebSocket in real time
6. **On action failure** — SelfHealingEngine tries: ① scroll down ② text-similarity search ③ ask user;
   then Gemini deep recovery with fresh screenshot re-analysis
7. **Frontend updates** the Screen Viewer, Reasoning Trail, Action Log, and Task Plan Panel live

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Lucide icons |
| Backend | Python 3.11, FastAPI, Uvicorn |
| AI | Gemini 1.5 Pro Vision via Google Vertex AI |
| Browser automation | Playwright (Chromium) |
| Computer vision | OpenCV (headless) |
| Real-time comms | WebSockets (native FastAPI) |
| Cloud hosting | Firebase Hosting + Google Cloud Run |
| CI/CD | Google Cloud Build |

---

## License

MIT

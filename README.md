# Snapdeal Virtual KAM — Aarav

A browser-based, voice-first AI Key Account Manager demo built with **FastAPI** and **Gemini Live**. Aarav speaks with a seller, investigates a sample business scenario, explains possible causes of a sales decline, and prepares mock business actions for seller approval.

## Live demo

**[Open Aarav — Snapdeal Virtual KAM](https://kam-wqma.onrender.com)**

The application is hosted as a Render Web Service. On Render's Free plan, the service may take about a minute to wake after a period of inactivity.

## Features

- Two-way browser voice conversation using the microphone and audio playback.
- English-only spoken responses while understanding English, Hindi and Hinglish input.
- Seller performance investigation using sample data.
- Read-only business tools for seller metrics, out-of-stock products and cancellation breakdown.
- Dynamic seller KPI dashboard and investigation details.
- Approval previews for restock tasks, WhatsApp summaries and follow-up calls.
- Mock action execution only after seller approval.
- SQLite follow-up records and a due-date monitor.
- **Test Follow-up Now** creates an explicitly simulated recovery report for demonstration.
- Voice-controlled call termination.

## Technology stack

- **Frontend:** HTML, CSS and JavaScript; browser microphone and audio APIs.
- **Backend:** Python, FastAPI and Uvicorn.
- **AI / voice:** Google Gemini Live API through the `google-genai` Python SDK.
- **Real-time communication:** Browser-to-FastAPI WebSocket (`/ws`) and a backend Gemini Live connection.
- **Business logic:** Python tool handlers in `tools.py` using sample seller data.
- **Follow-up storage:** SQLite through `followups.py`.

## Requirements

- Python 3.10 or newer.
- A Gemini API key with access to the configured Live model.
- Chrome or Edge with microphone permission.

## Run locally on Windows

Open PowerShell in the project directory.

Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-3.8-live
```

Do not commit or share `.env`. The repository includes `.env.example` as a configuration template.

Start the application:

```powershell
uvicorn main:app --reload
```

Open these local endpoints:

- App: <http://127.0.0.1:8000>
- Health check: <http://127.0.0.1:8000/health>
- Follow-up records: <http://127.0.0.1:8000/api/followups>
- Voice WebSocket: `ws://127.0.0.1:8000/ws` (used by the browser application)

Allow microphone access when the browser prompts you.

## Deploy on Render

This repository is deployed as a Render **Web Service**. The current live deployment is:

- **URL:** <https://kam-wqma.onrender.com>
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Root directory:** repository root (leave blank in Render when the application files are at the root).

Set the following environment variables in the Render service's **Environment** settings:

| Variable | Value |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key (keep it secret) |
| `GEMINI_MODEL` | `gemini-3.8-live` |

Do not put API keys in source code, README files, screenshots or Git commits. Add secrets through the hosting provider's environment-variable settings.

### Render Free-plan storage and availability note

The app currently stores follow-up data in the local SQLite file `kam_followups.db`. Render Free Web Services have an ephemeral filesystem. SQLite records created on the hosted service can be lost when the service spins down, restarts or is redeployed. The Free service also spins down after 15 minutes without inbound HTTP traffic or WebSocket messages and can take about a minute to start again on the next request.

This is acceptable for a short-lived prototype/demo, but **the hosted Free instance must not be treated as durable follow-up storage**. The local version stores its SQLite database in the project directory and retains records across ordinary local application restarts. For durable hosted data, move follow-up storage to a managed database such as PostgreSQL, or use a paid Render service with an appropriately mounted persistent disk and database path configuration.

The in-process follow-up scheduler only runs while the application process is active. It is a demo scheduler, not a guaranteed background job service.

## Follow-up demo

1. Start a voice session with Aarav.
2. Ask Aarav to schedule a follow-up in a few days.
3. Review and approve the follow-up preview on the dashboard.
4. The follow-up is stored in `kam_followups.db` in local mode.
5. Under **Follow-up Intelligence**, click **Test Follow-up Now**.
6. Review the generated report.

The immediate test report deliberately uses simulated recovery metrics. It is not based on fresh Snapdeal or seller transaction data and must not be presented as actual seller performance. The background scheduler only marks scheduled records as due; it does not fetch new seller metrics.

## Sample business scenario

The demo uses mock seller data to investigate a decline in sales:

| Metric | Last month | This month |
|---|---:|---:|
| Sales | ₹2,00,000 | ₹1,35,000 |
| Orders | 400 | 270 |
| Cancellation rate | 8% | 14% |
| Average selling price | ₹500 | ₹500 |
| Out-of-stock products | 5 | 18 |

Aarav can use this data to investigate lower order volume, increased cancellations and higher stock-outs. These are diagnostic clues, not proof of causation.

## Data and integration limitations

- Seller metrics, SKU-level details and cancellation reason percentages are sample/mock data.
- Any cancellation reason split or estimated lost-order/revenue figures are assumptions or estimates, not verified transaction-level facts.
- Restock tasks, WhatsApp summaries and follow-up calls are mock operations.
- No Snapdeal internal system, seller account, WhatsApp account, calendar or telephone system is connected.
- Seller approval is required before a mock action is recorded.
- The hosted Render Free SQLite database is temporary; see the storage note above.

## Architecture

```text
Browser
  |-- Microphone input / audio playback
  |-- Transcript and dynamic seller dashboard
  |-- Action approval previews and history
  |
  +---- WebSocket (/ws) ---- FastAPI backend
                               |-- Gemini Live API
                               |-- KamSession business tools (tools.py)
                               |-- Mock seller data (data.py)
                               |-- SQLite follow-up store (followups.py)
                               +-- Follow-up API and in-process scheduler
```

## Project files

- `main.py` — FastAPI application, Gemini Live session, WebSocket handling and approval flow.
- `tools.py` — seller investigation tools and mock action handlers.
- `data.py` — sample seller and product data.
- `prompt.py` — Aarav's system prompt and conversational behavior.
- `followups.py` — SQLite follow-up storage and simulated follow-up reports.
- `static/index.html` — browser interface.
- `test_agent_tools.py`, `test_followups.py` — local tests.
- `TECHNICAL_NOTE.md` — one-page AI and voice workflow explanation.
- `DEMO_SCRIPT.md` — suggested 1–2 minute demo walkthrough.

## Submission demo

See `DEMO_SCRIPT.md` for a concise 1–2 minute walkthrough and `TECHNICAL_NOTE.md` for the technical explanation. The live demo link above can be used to access the deployed browser-based voice experience.

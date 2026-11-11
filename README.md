# Snapdeal Virtual KAM — Aarav

A browser-based, voice-first AI Key Account Manager demo built with FastAPI and Gemini Live.

## Features

- Two-way browser voice conversation.
- English-only spoken responses while understanding English, Hindi and Hinglish.
- Seller performance investigation using mock metrics.
- Read-only tools for seller metrics, all out-of-stock products (or an explicitly requested top-N subset) and cancellation breakdown.
- Dynamic dashboard updates.
- Approval previews for restock (all, top five, or selected verified SKUs), WhatsApp-summary and follow-up actions.
- Mock action execution only after seller approval.
- Persistent SQLite follow-up records.
- Follow-up due-date monitoring.
- **Test Follow-up Now** creates an explicitly simulated recovery report for demo purposes.
- Voice-controlled call termination.

## Requirements

- Python 3.10+
- A Gemini API key with access to the configured Live model.
- Chrome or Edge with microphone permission.

## Setup on Windows

Open PowerShell in the project directory:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.env` in the project root:

```env
GEMINI_API_KEY=YOUR_NEW_API_KEY
GEMINI_MODEL=gemini-3.8-live
```

Do not commit or share `.env`.

Run:

```powershell
uvicorn main:app --reload
```

Open:

- App: http://127.0.0.1:8000
- Health check: http://127.0.0.1:8000/health
- Follow-up records: http://127.0.0.1:8000/api/followups

## Follow-up demo

1. Start a voice call.
2. Ask Aarav to schedule a follow-up in three days.
3. Approve the follow-up preview on the dashboard.
4. The record is saved in `kam_followups.db` with its baseline metrics.
5. Under **Follow-up Intelligence**, click **Test Follow-up Now**.
6. Review the generated report.

The immediate test report deliberately uses simulated recovery metrics. It is not fresh seller data and must not be presented as actual Snapdeal performance. The background scheduler only marks records due; a real analysis requires a live or refreshed seller data source.

## Data and integration limitations

- Seller metrics, SKU-level details and cancellation reason percentages are supplied mock data.
- Lost-order values are estimates.
- Restock tasks, WhatsApp messages and follow-up calls are mock operations.
- No Snapdeal internal system, WhatsApp account, calendar or phone system is connected.
- SQLite stores follow-up requests and reports locally. It is suitable for this local demo, not a multi-user production deployment.
- The app must remain running for its in-process due-date monitor to run. Saved records survive restarts.

## Architecture

```text
Browser microphone
       |
       v
WebSocket (/ws) <----> FastAPI backend
       |                     |
       |                     +---- Gemini Live API
       |                     |
       |                     +---- KamSession business tools
       |                     |
       |                     +---- SQLite follow-up store
       |
       +---- Audio playback, transcript, dynamic dashboard
       +---- Approval previews and mock action results
       +---- Follow-up report and simulated test
```

## Submission demo

See `DEMO_SCRIPT.md` for a concise 1–2 minute walkthrough and `TECHNICAL_NOTE.md` for the one-page technical explanation.

# elevenlabs-voice-agent

Production-ready deployment pattern for ElevenLabs Conversational AI, voice agent with real-time session analytics.

---

## Background

Built as a reference implementation for deploying ElevenLabs voice agents in an enterprise contact centre context. The demo scenario is a telco customer support agent (billing, plan changes, outage queries), chosen because it represents one of the highest-volume, highest-stakes use cases for voice AI in market.

The architecture reflects real enterprise constraints: API credentials never reach the browser, all session events are captured server-side, and the analytics layer surfaces the KPIs an ops team would actually monitor in production, containment rate, escalation triggers, turn depth, and session duration.

---

## What's built

```
Browser ──── ElevenLabs WebSocket (signed URL) ────▶ Maya voice agent
   │
   │  session summary (on call end)
   ▼
FastAPI backend
   ├── /api/signed-url     issues short-lived signed URLs (API key stays server-side)
   ├── /api/sessions       receives + stores completed session summaries
   └── /api/metrics        aggregates KPIs across sessions
```

| Component | Description |
|---|---|
| `main.py` | FastAPI server — signed URL issuance, session ingestion, metrics endpoint |
| `agent/session_tracker.py` | In-memory session store with KPI aggregation |
| `static/index.html` | Voice interface + live analytics dashboard (single file, zero build step) |

---

## Key design decisions

**Signed URL pattern** — The ElevenLabs API key is never sent to the browser. On call start, the frontend requests a short-lived signed WebSocket URL from the backend. This is the recommended production pattern for any deployment where the client is untrusted (web, mobile).

**Escalation detection** — The agent's system prompt includes a deterministic escalation phrase. The frontend detects this phrase in real-time transcript events and flags the session as escalated. In production, this signal feeds into routing logic and reporting pipelines.

**Voice-first system prompt design** — Agent instructions enforce concise, natural speech (2–3 sentence responses, no lists) and define explicit escalation triggers. These constraints matter in production: TTS systems perform significantly better with short, well-formed sentences.

**Stateless session summaries** — The frontend tracks turn count, escalation status, and transcript during the call, then POSTs a structured summary on disconnect. This pattern decouples call handling from analytics ingestion and works regardless of whether the session ends cleanly or drops.

---

## Setup

```bash
git clone https://github.com/your-username/elevenlabs-voice-agent-starter
cd elevenlabs-voice-agent-starter

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID
```

Run:
```bash
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000` — click **Start Call** and speak.

---

## Demo: client specific interface integrating ElevenLabs agent

<img width="1915" height="907" alt="image" src="https://github.com/user-attachments/assets/e93168ea-8741-4d4e-95d1-a0335e74af4f" />

---

## Configuration

| Variable | Description |
|---|---|
| `ELEVENLABS_API_KEY` | Your ElevenLabs API key (Profile → API Keys) |
| `ELEVENLABS_AGENT_ID` | Agent ID from ElevenAgents dashboard |
| `PORT` | Server port (default: `8000`) |

### API key scopes required

Minimum permissions for this project:

| Scope | Level |
|---|---|
| ElevenAgents | Write |
| Text to Speech | Access |
| Speech to Text | Access |
| Webhooks | Access |
| History | Read |
| User | Read |

Apply least-privilege and set a monthly credit cap on the key, especially in shared or staging environments.

---

## Extending to production

**Persist sessions to a database:**
```python
# In agent/session_tracker.py — replace the in-memory list:
# from google.cloud import bigquery
# client = bigquery.Client()
# client.insert_rows_json("project.dataset.sessions", [session_data])
```

**Restrict signed URL issuance by authenticated users:**
```python
# In main.py — add auth dependency:
# @app.get("/api/signed-url", dependencies=[Depends(verify_token)])
```

**Connect to a telephony layer (Twilio, Genesys):**
ElevenLabs Conversational AI supports SIP and PSTN via Twilio integration, the signed URL pattern in this project maps directly to that flow.

---

## Stack

`Python · FastAPI · httpx · ElevenLabs Conversational AI API · Vanilla JS (ES Modules)`

---

## Built With

- [ElevenLabs Conversational AI](https://elevenlabs.io) — voice agent deployment and STT/TTS APIs
- [ElevenAgents](https://elevenlabs.io/agents) — managed agent infrastructure

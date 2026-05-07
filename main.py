"""
main.py — ElevenLabs Voice Agent Demo Server

Responsibilities:
  1. Serve the frontend (static/index.html)
  2. Issue signed conversation URLs — keeps API key server-side (production pattern)
  3. Receive session summaries from the frontend on call completion
  4. Expose aggregated metrics for the live analytics dashboard

Run:
    uvicorn main:app --reload --port 8000
"""

import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agent.session_tracker import SessionTracker
from summariser import summarise_session

load_dotenv()

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="ElevenLabs Voice Agent Demo", version="1.0.0")
tracker = SessionTracker()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """Serve the voice agent frontend."""
    with open("static/index.html", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/signed-url")
async def get_signed_url() -> JSONResponse:
    """
    Exchange the server-side API key for a short-lived signed WebSocket URL.

    This is the recommended production pattern — the ElevenLabs API key never
    reaches the browser. The signed URL is single-use and expires after a short
    window, so it is safe to pass to the client.
    """
    agent_id = os.getenv("ELEVENLABS_AGENT_ID")
    api_key = os.getenv("ELEVENLABS_API_KEY")

    if not agent_id or not api_key:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": (
                    "Missing configuration. "
                    "Set ELEVENLABS_AGENT_ID and ELEVENLABS_API_KEY in .env"
                )
            },
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "https://api.elevenlabs.io/v1/convai/conversation/get_signed_url",
            params={"agent_id": agent_id},
            headers={"xi-api-key": api_key},
        )

    if response.status_code != 200:
        return JSONResponse(
            status_code=response.status_code,
            content={"error": "ElevenLabs API error", "detail": response.text},
        )

    return JSONResponse(content=response.json())


@app.post("/api/sessions", status_code=status.HTTP_201_CREATED)
async def record_session(request: Request) -> dict:
    """
    Receive a completed session summary from the frontend.

    Expected payload:
        session_id       str   — ElevenLabs conversation ID
        start_time       str   — ISO 8601 UTC
        end_time         str   — ISO 8601 UTC
        duration_seconds float
        turn_count       int   — number of user turns
        escalated        bool  — true if escalation phrase was detected
        transcript       list  — [{source, message, timestamp}]

    The transcript is flattened and passed to the summariser, which calls
    Claude to produce a structured summary card stored alongside the session.
    The summariser fails gracefully — a fallback dict is stored on any error.
    """
    body = await request.json()

    # Flatten transcript list → plain text for the summariser
    transcript_text = "\n".join(
        f"{t.get('source', 'unknown').upper()}: {t.get('message', '')}"
        for t in body.get("transcript", [])
    )
    body["summary"] = summarise_session(
        transcript=transcript_text,
        escalated=bool(body.get("escalated", False)),
    )

    tracker.add_session(body)
    return {"status": "recorded", "total_sessions": len(tracker.get_sessions())}


@app.get("/api/metrics")
async def get_metrics() -> dict:
    """Return aggregated KPIs across all sessions recorded this runtime."""
    return tracker.get_metrics()


@app.get("/api/sessions")
async def get_sessions() -> list:
    """Return all sessions, most recent first."""
    return tracker.get_sessions()
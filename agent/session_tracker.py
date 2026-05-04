"""
session_tracker.py

In-memory session store and metrics aggregator.
Receives structured session summaries from the frontend on call completion
and exposes aggregated KPIs via the /api/metrics endpoint.

In production, replace the in-memory list with a database write
(e.g. BigQuery, Postgres) for persistence across restarts.
"""

import statistics
from datetime import datetime
from typing import Any


class SessionTracker:
    def __init__(self) -> None:
        self._sessions: list[dict[str, Any]] = []

    # ── Ingestion ────────────────────────────────────────────────────────────

    def add_session(self, session_data: dict[str, Any]) -> None:
        """Store a completed session summary received from the frontend."""
        session_data["recorded_at"] = datetime.utcnow().isoformat()
        self._sessions.append(session_data)

    # ── Retrieval ────────────────────────────────────────────────────────────

    def get_sessions(self) -> list[dict[str, Any]]:
        """Return all sessions, most recent first."""
        return list(reversed(self._sessions))

    def get_metrics(self) -> dict[str, Any]:
        """
        Aggregate KPIs across all recorded sessions.

        Returns:
            total_sessions       int   — all sessions recorded this runtime
            containment_rate     float — % sessions resolved without escalation
            escalation_rate      float — % sessions that triggered escalation
            total_escalations    int   — raw escalation count
            avg_turns            float — mean user turns per session
            avg_duration_seconds float — mean session length in seconds
        """
        if not self._sessions:
            return {
                "total_sessions": 0,
                "containment_rate": 0.0,
                "escalation_rate": 0.0,
                "total_escalations": 0,
                "avg_turns": 0.0,
                "avg_duration_seconds": 0.0,
            }

        total = len(self._sessions)
        escalations = sum(1 for s in self._sessions if s.get("escalated", False))
        turns = [s.get("turn_count", 0) for s in self._sessions]
        durations = [s.get("duration_seconds", 0) for s in self._sessions]

        return {
            "total_sessions": total,
            "containment_rate": round((total - escalations) / total * 100, 1),
            "escalation_rate": round(escalations / total * 100, 1),
            "total_escalations": escalations,
            "avg_turns": round(statistics.mean(turns), 1) if turns else 0.0,
            "avg_duration_seconds": round(statistics.mean(durations), 1) if durations else 0.0,
        }

from __future__ import annotations
import json, os
from datetime import datetime, timezone
from typing import Any

DB_URL = os.getenv("DATABASE_URL", "")

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    brand TEXT NOT NULL DEFAULT 'Other',
    channel TEXT NOT NULL,
    sender TEXT,
    received_at TIMESTAMPTZ,
    text TEXT,
    raw_payload JSONB,
    status TEXT NOT NULL DEFAULT 'queued',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS decisions (
    id BIGSERIAL PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    intent TEXT NOT NULL,
    entities JSONB NOT NULL DEFAULT '{}'::jsonb,
    next_action TEXT NOT NULL,
    handler TEXT NOT NULL,
    priority TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    human_review BOOLEAN NOT NULL,
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    route TEXT NOT NULL,
    model TEXT,
    latency_ms DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel);
CREATE INDEX IF NOT EXISTS idx_decisions_message_id ON decisions(message_id);
"""

def _conn():
    if not DB_URL:
        return None
    import psycopg
    return psycopg.connect(DB_URL, autocommit=True)

def init_db() -> bool:
    conn = _conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
        return True
    finally:
        conn.close()

def save_message(message: dict[str, Any]) -> bool:
    conn = _conn()
    if conn is None:
        return False
    try:
        received = message.get("received_at")
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO messages(id,brand,channel,sender,received_at,text,raw_payload,status)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,'queued')
                   ON CONFLICT(id) DO UPDATE SET brand=EXCLUDED.brand, channel=EXCLUDED.channel,
                   sender=EXCLUDED.sender, received_at=EXCLUDED.received_at, text=EXCLUDED.text,
                   raw_payload=EXCLUDED.raw_payload, updated_at=NOW()""",
                (message["id"], message.get("brand", "Other"), message.get("channel", "unknown"),
                 message.get("sender"), received, message.get("text"), json.dumps(message)),
            )
        return True
    finally:
        conn.close()

def mark_message(message_id: str, status: str) -> None:
    conn = _conn()
    if conn is None: return
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE messages SET status=%s, updated_at=NOW() WHERE id=%s", (status, message_id))
    finally:
        conn.close()

def save_decision(message: dict[str, Any], result: dict[str, Any], route: str, model: str | None, latency_ms: float | None) -> bool:
    conn = _conn()
    if conn is None: return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO decisions(message_id,intent,entities,next_action,handler,priority,confidence,human_review,reasons,route,model,latency_ms)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (message["id"], result["intent"], json.dumps(result.get("entities", {})), result["next_action"],
                 result["handler"], result["priority"], result["confidence"], result["human_review"],
                 json.dumps(result.get("reasons", [])), route, model, latency_ms),
            )
        mark_message(message["id"], "processed")
        return True
    finally:
        conn.close()

def recent_decisions(limit: int = 100) -> list[dict[str, Any]]:
    conn = _conn()
    if conn is None: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT message_id,intent,handler,priority,confidence,human_review,route,model,latency_ms,created_at
                          FROM decisions ORDER BY created_at DESC LIMIT %s""", (limit,))
            cols=[d.name for d in cur.description]
            return [dict(zip(cols,row)) for row in cur.fetchall()]
    finally:
        conn.close()

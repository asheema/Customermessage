from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path('audit.db')

def init_db():
    with sqlite3.connect(DB) as con:
        con.execute('CREATE TABLE IF NOT EXISTS audit (ts TEXT, user TEXT, role TEXT, action TEXT, message_id TEXT, route TEXT, intent TEXT, confidence REAL, human_review INTEGER)')

def log_event(user, action, result=None, route=''):
    init_db()
    with sqlite3.connect(DB) as con:
        con.execute('INSERT INTO audit VALUES (?,?,?,?,?,?,?,?,?)', (
            datetime.now(timezone.utc).isoformat(), getattr(user,'username',getattr(user,'email','anonymous')), getattr(user,'role',''), action,
            getattr(result,'id',None) if result else None, route, getattr(result,'intent',None) if result else None,
            getattr(result,'confidence',None) if result else None, int(getattr(result,'human_review',False)) if result else None))

def recent(limit=100):
    init_db()
    with sqlite3.connect(DB) as con:
        rows = con.execute('SELECT ts,user,role,action,message_id,route,intent,confidence,human_review FROM audit ORDER BY ts DESC LIMIT ?', (limit,)).fetchall()
    return rows

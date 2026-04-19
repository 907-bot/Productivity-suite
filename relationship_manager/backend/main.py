"""
Relationship Manager - FastAPI Backend
Stack: FastAPI + SQLite/Postgres
"""

import os
import uuid
import sys
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Add root to search path to ensure db_helper can be found
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

try:
    from db_helper import DB
except ImportError:
    import db_helper
    DB = db_helper.DB

load_dotenv()

app = FastAPI(title="Relationship Manager API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relationship.db")

def init_db():
    queries = [
        "CREATE TABLE IF NOT EXISTS contacts (id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT DEFAULT 'Friend', notes TEXT DEFAULT '', phone TEXT DEFAULT '', email TEXT DEFAULT '', birthday TEXT DEFAULT '', sentiment TEXT DEFAULT 'Neutral', health_score INTEGER DEFAULT 75, last_contact TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS interactions (id TEXT PRIMARY KEY, contact_id TEXT, type TEXT DEFAULT 'Message', notes TEXT DEFAULT '', sentiment TEXT DEFAULT 'Neutral', created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, contact_id TEXT, contact_name TEXT NOT NULL, title TEXT NOT NULL, event_date TEXT NOT NULL, type TEXT DEFAULT 'Birthday', reminder_days INTEGER DEFAULT 3, notes TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS message_templates (id TEXT PRIMARY KEY, name TEXT NOT NULL, body TEXT NOT NULL, tone TEXT DEFAULT 'Warm & Friendly', category TEXT DEFAULT 'General', created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    ]
    for q in queries:
        DB.execute(DB_PATH, q)

init_db()

# -- Models --
class ContactIn(BaseModel):
    name: str
    category: str = "Friend"
    notes: str = ""
    phone: str = ""
    email: str = ""
    birthday: str = ""

class ContactUpdateIn(BaseModel):
    health_score: Optional[int] = None
    sentiment: Optional[str] = None
    notes: Optional[str] = None

# -- Routes --
@app.get("/health")
def health():
    return {"status": "ok", "db": "postgres" if os.getenv("DATABASE_URL") else "sqlite"}

@app.get("/dashboard")
def dashboard():
    contacts = DB.execute(DB_PATH, "SELECT * FROM contacts ORDER BY health_score DESC", fetch=True) or []
    events = DB.execute(DB_PATH, "SELECT * FROM events ORDER BY event_date ASC", fetch=True) or []
    recent_interactions = DB.execute(DB_PATH, "SELECT i.*, c.name as contact_name FROM interactions i LEFT JOIN contacts c ON i.contact_id=c.id ORDER BY i.created_at DESC LIMIT 5", fetch=True) or []
    
    return {
        "total_contacts": len(contacts),
        "contacts": contacts,
        "upcoming_events": events[:5],
        "recent_interactions": recent_interactions,
        "avg_health_score": round(sum(c["health_score"] for c in contacts) / len(contacts), 1) if contacts else 0
    }

@app.get("/contacts")
def get_contacts():
    return {"items": DB.execute(DB_PATH, "SELECT * FROM contacts ORDER BY health_score DESC", fetch=True) or []}

@app.post("/contacts")
def add_contact(c: ContactIn):
    cid = str(uuid.uuid4())
    DB.execute(DB_PATH, "INSERT INTO contacts (id,name,category,notes,phone,email,birthday) VALUES (?,?,?,?,?,?,?)", (cid, c.name, c.category, c.notes, c.phone, c.email, c.birthday))
    return {"id": cid}

@app.delete("/contacts/{cid}")
def delete_contact(cid: str):
    DB.execute(DB_PATH, "DELETE FROM contacts WHERE id=?", (cid,))
    return {"status": "deleted"}

@app.get("/message-templates")
def get_message_templates():
    return {"templates": DB.execute(DB_PATH, "SELECT * FROM message_templates ORDER BY category, created_at DESC", fetch=True) or []}

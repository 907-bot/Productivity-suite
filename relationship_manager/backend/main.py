"""
Relationship Manager - FastAPI Backend
Stack: FastAPI + SQLite
Features: Contacts, Interaction Timeline, Birthday/Event Reminders, Health Score Editor
"""

import os
import uuid
import sqlite3
from datetime import datetime, date, timedelta
from typing import Optional
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Relationship Manager API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relationship.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    # 1. Create tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Friend',
            notes TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            birthday TEXT DEFAULT '',
            sentiment TEXT DEFAULT 'Neutral',
            health_score INTEGER DEFAULT 75,
            last_contact TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS interactions (
            id TEXT PRIMARY KEY,
            contact_id TEXT,
            type TEXT DEFAULT 'Message',
            notes TEXT DEFAULT '',
            sentiment TEXT DEFAULT 'Neutral',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            contact_id TEXT,
            contact_name TEXT NOT NULL,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            type TEXT DEFAULT 'Birthday',
            reminder_days INTEGER DEFAULT 3,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS message_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            body TEXT NOT NULL,
            tone TEXT DEFAULT 'Warm & Friendly',
            category TEXT DEFAULT 'General',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # 2. Migration
    tables_to_check = {
        "contacts": ["category", "notes", "phone", "email", "birthday", "sentiment", "health_score", "last_contact", "created_at"],
        "interactions": ["contact_id", "type", "notes", "sentiment", "created_at"],
        "events": ["contact_id", "contact_name", "title", "event_date", "type", "reminder_days", "notes", "created_at"],
        "message_templates": ["name", "body", "tone", "category", "created_at"]
    }
    for table, cols in tables_to_check.items():
        existing_cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        for col in cols:
            if col not in existing_cols:
                if col == "created_at":
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN created_at TEXT")
                elif col == "health_score":
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN health_score INTEGER DEFAULT 75")
                elif col == "reminder_days":
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN reminder_days INTEGER DEFAULT 3")
                else:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")

    if conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0:
        conn.executemany("INSERT INTO contacts (id,name,category,notes,sentiment,health_score,birthday) VALUES (?,?,?,?,?,?,?)", [
            (str(uuid.uuid4()), "Priya (Best Friend)", "Friend", "Long-time friend, loves travel and movies", "Positive", 92, "1996-03-15"),
            (str(uuid.uuid4()), "Rahul (Manager)", "Professional", "Direct manager, prefers formal communication", "Neutral", 70, ""),
            (str(uuid.uuid4()), "Mom", "Family", "Call every Sunday, remembers birthdays", "Positive", 98, "1968-07-22"),
        ])
    if conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0:
        conn.executemany("INSERT INTO events (id,contact_name,title,event_date,type) VALUES (?,?,?,?,?)", [
            (str(uuid.uuid4()), "Priya (Best Friend)", "Priya's Birthday", "2026-03-15", "Birthday"),
            (str(uuid.uuid4()), "Mom", "Mom's Birthday", "2026-07-22", "Birthday"),
            (str(uuid.uuid4()), "Rahul (Manager)", "Work Anniversary", "2026-06-01", "Anniversary"),
        ])
    if conn.execute("SELECT COUNT(*) FROM message_templates").fetchone()[0] == 0:
        conn.executemany("INSERT INTO message_templates (id,name,body,tone,category) VALUES (?,?,?,?,?)", [
            (str(uuid.uuid4()), "Happy Birthday", "Wishing you a wonderful birthday! Hope your day is filled with joy and laughter 🎂🎉", "Warm & Friendly", "Birthday"),
            (str(uuid.uuid4()), "Checking In", "Hey! Just dropped by to see how you're doing. Hope everything's going well on your end 😊", "Casual", "General"),
            (str(uuid.uuid4()), "Thank You", "Thank you so much for your help! It really made a difference and I truly appreciate it.", "Professional", "Appreciation"),
        ])
    conn.commit()
    conn.close()

init_db()

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

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
    phone: Optional[str] = None
    email: Optional[str] = None
    birthday: Optional[str] = None

class InteractionIn(BaseModel):
    contact_id: str
    type: str = "Message"
    notes: str = ""
    sentiment: str = "Neutral"

class EventIn(BaseModel):
    contact_id: Optional[str] = None
    contact_name: str
    title: str
    event_date: str
    type: str = "Birthday"
    reminder_days: int = 3
    notes: str = ""

class TemplateIn(BaseModel):
    name: str
    body: str
    tone: str = "Warm & Friendly"
    category: str = "General"

@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0"}

@app.get("/contacts")
def get_contacts():
    with get_db() as db:
        contacts = [dict(r) for r in db.execute("SELECT * FROM contacts ORDER BY health_score DESC").fetchall()]
        return {"items": contacts}

@app.post("/contacts")
def add_contact(c: ContactIn):
    with get_db() as db:
        cid = str(uuid.uuid4())
        db.execute("INSERT INTO contacts (id,name,category,notes,phone,email,birthday) VALUES (?,?,?,?,?,?,?)",
                   (cid, c.name, c.category, c.notes, c.phone, c.email, c.birthday))
        return {"id": cid, "status": "created"}

@app.patch("/contacts/{cid}")
def update_contact(cid: str, u: ContactUpdateIn):
    with get_db() as db:
        updates = {k: v for k, v in u.dict().items() if v is not None}
        if not updates:
            return {"status": "no changes"}
        set_clause = ", ".join(f"{k}=?" for k in updates)
        db.execute(f"UPDATE contacts SET {set_clause} WHERE id=?", list(updates.values()) + [cid])
        return {"status": "updated"}

@app.delete("/contacts/{cid}")
def delete_contact(cid: str):
    with get_db() as db:
        db.execute("DELETE FROM contacts WHERE id=?", (cid,))
        db.execute("DELETE FROM interactions WHERE contact_id=?", (cid,))
        return {"status": "deleted"}

# -- Interactions / Timeline --
@app.get("/contacts/{cid}/timeline")
def get_contact_timeline(cid: str):
    with get_db() as db:
        contact = db.execute("SELECT * FROM contacts WHERE id=?", (cid,)).fetchone()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        interactions = [dict(r) for r in db.execute(
            "SELECT * FROM interactions WHERE contact_id=? ORDER BY created_at DESC LIMIT 30", (cid,)).fetchall()]
        return {"contact": dict(contact), "timeline": interactions}

@app.post("/interactions")
def log_interaction(i: InteractionIn):
    with get_db() as db:
        iid = str(uuid.uuid4())
        db.execute("INSERT INTO interactions (id,contact_id,type,notes,sentiment) VALUES (?,?,?,?,?)",
                   (iid, i.contact_id, i.type, i.notes, i.sentiment))
        db.execute("UPDATE contacts SET last_contact=? WHERE id=?", (date.today().isoformat(), i.contact_id))
        # Update health score based on recency
        last_30_count = db.execute(
            "SELECT COUNT(*) FROM interactions WHERE contact_id=? AND created_at >= date('now','-30 days')", (i.contact_id,)).fetchone()[0]
        new_score = min(100, 50 + last_30_count * 10)
        db.execute("UPDATE contacts SET health_score=? WHERE id=?", (new_score, i.contact_id))
        return {"id": iid, "status": "logged"}

@app.get("/interactions/recent")
def get_recent_interactions():
    with get_db() as db:
        interactions = [dict(r) for r in db.execute(
            "SELECT i.*, c.name as contact_name FROM interactions i LEFT JOIN contacts c ON i.contact_id=c.id ORDER BY i.created_at DESC LIMIT 20"
        ).fetchall()]
        return {"interactions": interactions}

# -- Events & Birthdays --
@app.get("/events")
def get_events():
    with get_db() as db:
        events = [dict(r) for r in db.execute("SELECT * FROM events ORDER BY event_date ASC").fetchall()]
        today = date.today()
        for e in events:
            try:
                event_date = datetime.strptime(e["event_date"], "%Y-%m-%d").date()
                # Find next occurrence this year
                this_year = event_date.replace(year=today.year)
                if this_year < today:
                    this_year = this_year.replace(year=today.year + 1)
                e["days_until"] = (this_year - today).days
                e["upcoming"] = e["days_until"] <= 30
            except:
                e["days_until"] = 999
                e["upcoming"] = False
        events.sort(key=lambda x: x["days_until"])
        return {"events": events}

@app.get("/events/upcoming")
def get_upcoming_events():
    """Events in the next 30 days"""
    with get_db() as db:
        events = [dict(r) for r in db.execute("SELECT * FROM events ORDER BY event_date ASC").fetchall()]
        today = date.today()
        upcoming = []
        for e in events:
            try:
                event_date = datetime.strptime(e["event_date"], "%Y-%m-%d").date()
                this_year = event_date.replace(year=today.year)
                if this_year < today:
                    this_year = this_year.replace(year=today.year + 1)
                days_until = (this_year - today).days
                if days_until <= 30:
                    e["days_until"] = days_until
                    upcoming.append(e)
            except:
                pass
        upcoming.sort(key=lambda x: x["days_until"])
        return {"upcoming": upcoming, "count": len(upcoming)}

@app.post("/events")
def add_event(e: EventIn):
    with get_db() as db:
        eid = str(uuid.uuid4())
        db.execute("INSERT INTO events (id,contact_id,contact_name,title,event_date,type,reminder_days,notes) VALUES (?,?,?,?,?,?,?,?)",
                   (eid, e.contact_id or "", e.contact_name, e.title, e.event_date, e.type, e.reminder_days, e.notes))
        return {"id": eid, "status": "created"}

@app.delete("/events/{eid}")
def delete_event(eid: str):
    with get_db() as db:
        db.execute("DELETE FROM events WHERE id=?", (eid,))
        return {"status": "deleted"}

# -- Dashboard --
@app.get("/dashboard")
def dashboard():
    with get_db() as db:
        contacts = [dict(r) for r in db.execute("SELECT * FROM contacts ORDER BY health_score DESC").fetchall()]
        events = [dict(r) for r in db.execute("SELECT * FROM events ORDER BY event_date ASC").fetchall()]
        recent_interactions = [dict(r) for r in db.execute(
            "SELECT i.*, c.name as contact_name FROM interactions i LEFT JOIN contacts c ON i.contact_id=c.id ORDER BY i.created_at DESC LIMIT 5"
        ).fetchall()]

        today = date.today()
        upcoming_events = []
        for e in events:
            try:
                event_date = datetime.strptime(e["event_date"], "%Y-%m-%d").date()
                this_year = event_date.replace(year=today.year)
                if this_year < today:
                    this_year = this_year.replace(year=today.year + 1)
                days_until = (this_year - today).days
                if days_until <= 30:
                    e["days_until"] = days_until
                    upcoming_events.append(e)
            except:
                pass
        upcoming_events.sort(key=lambda x: x["days_until"])

        # Contacts needing attention (health score < 70 or not contacted in 14 days)
        needs_attention = []
        for c in contacts:
            days_since = None
            if c["last_contact"]:
                try:
                    last = datetime.strptime(c["last_contact"], "%Y-%m-%d").date()
                    days_since = (today - last).days
                except:
                    pass
            if c["health_score"] < 70 or (days_since is not None and days_since > 14):
                needs_attention.append({**c, "days_since_contact": days_since})

        return {
            "total_contacts": len(contacts),
            "contacts": contacts,
            "upcoming_events": upcoming_events[:5],
            "recent_interactions": recent_interactions,
            "needs_attention": needs_attention[:5],
            "avg_health_score": round(sum(c["health_score"] for c in contacts) / len(contacts), 1) if contacts else 0
        }

# -- Message Templates --
@app.get("/templates")
def get_templates():
    with get_db() as db:
        templates = [dict(r) for r in db.execute("SELECT * FROM templates ORDER BY created_at DESC").fetchall()]
        return {"templates": templates}

@app.post("/templates")
def add_template(t: TemplateIn):
    with get_db() as db:
        # Check if table name might need correction
        tid = str(uuid.uuid4())
        db.execute("INSERT INTO message_templates (id,name,body,tone,category) VALUES (?,?,?,?,?)",
                   (tid, t.name, t.body, t.tone, t.category))
        return {"id": tid, "status": "created"}

@app.get("/message-templates")
def get_message_templates():
    with get_db() as db:
        templates = [dict(r) for r in db.execute("SELECT * FROM message_templates ORDER BY category, created_at DESC").fetchall()]
        return {"templates": templates}

@app.post("/message-templates")
def add_message_template(t: TemplateIn):
    with get_db() as db:
        tid = str(uuid.uuid4())
        db.execute("INSERT INTO message_templates (id,name,body,tone,category) VALUES (?,?,?,?,?)",
                   (tid, t.name, t.body, t.tone, t.category))
        return {"id": tid, "status": "created"}

@app.delete("/message-templates/{tid}")
def delete_template(tid: str):
    with get_db() as db:
        db.execute("DELETE FROM message_templates WHERE id=?", (tid,))
        return {"status": "deleted"}

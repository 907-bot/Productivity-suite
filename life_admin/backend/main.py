"""
Life Admin Manager - FastAPI Backend
Stack: FastAPI + SQLite
Features: Tasks, Bills, Reminders, Priority Matrix, Productivity Stats
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

# -- App --
app = FastAPI(title="Life Admin API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# -- Database --
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "life_admin.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    # 1. Create tables if not exist
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            priority TEXT DEFAULT 'today',
            quadrant TEXT DEFAULT 'q2',
            due TEXT,
            done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS bills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            due TEXT,
            status TEXT DEFAULT 'due',
            recurring INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS reminders (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            remind_at TEXT,
            repeat TEXT DEFAULT 'none',
            done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_logs (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            tasks_done INTEGER DEFAULT 0,
            focus_minutes INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    
    # 2. Migration: Add columns if table existed before schema change
    tables_to_check = {
        "tasks": ["priority", "quadrant", "due", "done", "created_at"],
        "bills": ["due", "status", "recurring", "created_at"],
        "reminders": ["remind_at", "repeat", "done", "created_at"],
        "daily_logs": ["tasks_done", "focus_minutes", "notes", "created_at"]
    }
    
    for table, cols in tables_to_check.items():
        existing_cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        for col in cols:
            if col not in existing_cols:
                # Basic migration
                if col == "created_at":
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN created_at TEXT")
                elif col in ("done", "recurring", "tasks_done", "focus_minutes"):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} INTEGER DEFAULT 0")
                else:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")

    # Seed data
    if conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0:
        conn.executemany("INSERT INTO tasks (id,text,priority,quadrant) VALUES (?,?,?,?)", [
            (str(uuid.uuid4()), "Review monthly expenses", "urgent", "q1"),
            (str(uuid.uuid4()), "Call dentist for appointment", "today", "q2"),
            (str(uuid.uuid4()), "Renew gym membership", "low", "q3"),
            (str(uuid.uuid4()), "Sort old emails", "low", "q4"),
        ])
    if conn.execute("SELECT COUNT(*) FROM bills").fetchone()[0] == 0:
        conn.executemany("INSERT INTO bills (id,name,amount,status,recurring) VALUES (?,?,?,?,?)", [
            (str(uuid.uuid4()), "Electricity Bill", 2400, "due", 1),
            (str(uuid.uuid4()), "Netflix", 649, "paid", 1),
            (str(uuid.uuid4()), "Internet", 999, "overdue", 1),
        ])
    if conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0] == 0:
        conn.executemany("INSERT INTO reminders (id,text,remind_at,repeat) VALUES (?,?,?,?)", [
            (str(uuid.uuid4()), "Take vitamins", "2026-04-20 09:00", "daily"),
            (str(uuid.uuid4()), "Weekly review", "2026-04-21 10:00", "weekly"),
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

# -- Models --
class TaskIn(BaseModel):
    text: str
    priority: str = "today"
    quadrant: str = "q2"
    due: Optional[str] = None

class BillIn(BaseModel):
    name: str
    amount: float
    due: Optional[str] = None
    recurring: int = 0

class ReminderIn(BaseModel):
    text: str
    remind_at: Optional[str] = None
    repeat: str = "none"

class DailyLogIn(BaseModel):
    date: str
    tasks_done: int = 0
    focus_minutes: int = 0
    notes: str = ""

# -- Routes --
@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0"}

@app.get("/dashboard")
def dashboard():
    with get_db() as db:
        tasks = [dict(r) for r in db.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()]
        bills = [dict(r) for r in db.execute("SELECT * FROM bills ORDER BY created_at DESC").fetchall()]
        reminders = [dict(r) for r in db.execute("SELECT * FROM reminders WHERE done=0 ORDER BY remind_at ASC LIMIT 5").fetchall()]
        pending = sum(1 for t in tasks if not t["done"])
        completed = sum(1 for t in tasks if t["done"])
        overdue_bills = [b for b in bills if b["status"] == "overdue"]
        amount_due = sum(b["amount"] for b in bills if b["status"] in ("due","overdue"))
        hour = datetime.now().hour
        greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"

        # Productivity streak (days with tasks done)
        streak = 0
        for i in range(30):
            d = (date.today() - timedelta(days=i)).isoformat()
            row = db.execute("SELECT tasks_done FROM daily_logs WHERE date=?", (d,)).fetchone()
            if row and row[0] > 0:
                streak += 1
            elif i > 0:
                break

        # This week stats
        week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        week_logs = [dict(r) for r in db.execute("SELECT * FROM daily_logs WHERE date >= ?", (week_start,)).fetchall()]
        week_focus = sum(l["focus_minutes"] for l in week_logs)

        return {
            "greeting": greeting,
            "tasks": {"pending": pending, "completed": completed, "items": tasks},
            "bills": {"overdue": len(overdue_bills), "amount_due": amount_due, "items": bills},
            "reminders": {"count": len(reminders), "items": reminders},
            "productivity": {"streak": streak, "week_focus_minutes": week_focus}
        }

# -- Tasks --
@app.get("/tasks")
def get_tasks():
    with get_db() as db:
        tasks = [dict(r) for r in db.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()]
        return {"tasks": tasks}

@app.get("/tasks/matrix")
def get_priority_matrix():
    """Return tasks organized by Eisenhower quadrant"""
    with get_db() as db:
        tasks = [dict(r) for r in db.execute("SELECT * FROM tasks WHERE done=0").fetchall()]
        matrix = {"q1": [], "q2": [], "q3": [], "q4": []}
        for t in tasks:
            q = t.get("quadrant", "q2")
            if q in matrix:
                matrix[q].append(t)
        return {
            "matrix": matrix,
            "labels": {
                "q1": "Urgent & Important",
                "q2": "Not Urgent but Important",
                "q3": "Urgent but Not Important",
                "q4": "Not Urgent & Not Important"
            }
        }

@app.post("/tasks")
def add_task(t: TaskIn):
    with get_db() as db:
        tid = str(uuid.uuid4())
        db.execute("INSERT INTO tasks (id,text,priority,quadrant,due) VALUES (?,?,?,?,?)",
                   (tid, t.text, t.priority, t.quadrant, t.due))
        return {"id": tid, "status": "created"}

@app.patch("/tasks/{tid}/toggle")
def toggle_task(tid: str):
    with get_db() as db:
        db.execute("UPDATE tasks SET done = CASE WHEN done=1 THEN 0 ELSE 1 END WHERE id=?", (tid,))
        # Update daily log
        today = date.today().isoformat()
        done_count = db.execute("SELECT COUNT(*) FROM tasks WHERE done=1 AND date(created_at)=?", (today,)).fetchone()[0]
        existing = db.execute("SELECT id FROM daily_logs WHERE date=?", (today,)).fetchone()
        if existing:
            db.execute("UPDATE daily_logs SET tasks_done=? WHERE date=?", (done_count, today))
        else:
            db.execute("INSERT INTO daily_logs (id,date,tasks_done) VALUES (?,?,?)", (str(uuid.uuid4()), today, done_count))
        return {"status": "toggled"}

@app.delete("/tasks/{tid}")
def delete_task(tid: str):
    with get_db() as db:
        db.execute("DELETE FROM tasks WHERE id=?", (tid,))
        return {"status": "deleted"}

# -- Bills --
@app.get("/bills")
def get_bills():
    with get_db() as db:
        bills = [dict(r) for r in db.execute("SELECT * FROM bills ORDER BY created_at DESC").fetchall()]
        return {"bills": bills}

@app.post("/bills")
def add_bill(b: BillIn):
    with get_db() as db:
        bid = str(uuid.uuid4())
        db.execute("INSERT INTO bills (id,name,amount,due,recurring) VALUES (?,?,?,?,?)",
                   (bid, b.name, b.amount, b.due, b.recurring))
        return {"id": bid, "status": "created"}

@app.patch("/bills/{bid}/pay")
def pay_bill(bid: str):
    with get_db() as db:
        db.execute("UPDATE bills SET status='paid' WHERE id=?", (bid,))
        return {"status": "paid"}

@app.delete("/bills/{bid}")
def delete_bill(bid: str):
    with get_db() as db:
        db.execute("DELETE FROM bills WHERE id=?", (bid,))
        return {"status": "deleted"}

# -- Reminders --
@app.get("/reminders")
def get_reminders():
    with get_db() as db:
        reminders = [dict(r) for r in db.execute("SELECT * FROM reminders ORDER BY remind_at ASC").fetchall()]
        return {"reminders": reminders}

@app.post("/reminders")
def add_reminder(r: ReminderIn):
    with get_db() as db:
        rid = str(uuid.uuid4())
        db.execute("INSERT INTO reminders (id,text,remind_at,repeat) VALUES (?,?,?,?)",
                   (rid, r.text, r.remind_at, r.repeat))
        return {"id": rid, "status": "created"}

@app.patch("/reminders/{rid}/done")
def mark_reminder_done(rid: str):
    with get_db() as db:
        db.execute("UPDATE reminders SET done=1 WHERE id=?", (rid,))
        return {"status": "done"}

@app.delete("/reminders/{rid}")
def delete_reminder(rid: str):
    with get_db() as db:
        db.execute("DELETE FROM reminders WHERE id=?", (rid,))
        return {"status": "deleted"}

# -- Productivity Logs --
@app.get("/productivity/stats")
def productivity_stats():
    with get_db() as db:
        # Last 30 days
        logs = []
        for i in range(29, -1, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            row = db.execute("SELECT * FROM daily_logs WHERE date=?", (d,)).fetchone()
            done = db.execute("SELECT COUNT(*) FROM tasks WHERE done=1").fetchone()[0]
            logs.append({
                "date": d,
                "tasks_done": row["tasks_done"] if row else 0,
                "focus_minutes": row["focus_minutes"] if row else 0,
            })
        total_tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        done_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE done=1").fetchone()[0]
        return {
            "daily_logs": logs,
            "total_tasks": total_tasks,
            "done_tasks": done_tasks,
            "completion_rate": round((done_tasks / total_tasks * 100) if total_tasks else 0, 1)
        }

@app.post("/productivity/log")
def log_productivity(l: DailyLogIn):
    with get_db() as db:
        existing = db.execute("SELECT id FROM daily_logs WHERE date=?", (l.date,)).fetchone()
        if existing:
            db.execute("UPDATE daily_logs SET tasks_done=?, focus_minutes=?, notes=? WHERE date=?",
                       (l.tasks_done, l.focus_minutes, l.notes, l.date))
        else:
            db.execute("INSERT INTO daily_logs (id,date,tasks_done,focus_minutes,notes) VALUES (?,?,?,?,?)",
                       (str(uuid.uuid4()), l.date, l.tasks_done, l.focus_minutes, l.notes))
        return {"status": "logged"}

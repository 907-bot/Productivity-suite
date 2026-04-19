"""
Life Admin Manager - FastAPI Backend
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
    # If standard import fails, try direct path import
    import db_helper
    DB = db_helper.DB

load_dotenv()

app = FastAPI(title="Life Admin API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "life_admin.db")

def init_db():
    queries = [
        "CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, text TEXT NOT NULL, priority TEXT DEFAULT 'today', quadrant TEXT DEFAULT 'q2', due TEXT, done INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS bills (id TEXT PRIMARY KEY, name TEXT NOT NULL, amount REAL NOT NULL, due TEXT, status TEXT DEFAULT 'due', recurring INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS reminders (id TEXT PRIMARY KEY, text TEXT NOT NULL, remind_at TEXT, repeat TEXT DEFAULT 'none', done INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS daily_logs (id TEXT PRIMARY KEY, date TEXT NOT NULL, tasks_done INTEGER DEFAULT 0, focus_minutes INTEGER DEFAULT 0, notes TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    ]
    for q in queries:
        DB.execute(DB_PATH, q)
    
    if not DB.execute(DB_PATH, "SELECT id FROM tasks LIMIT 1", fetch=True):
        DB.execute(DB_PATH, "INSERT INTO tasks (id,text,priority,quadrant) VALUES (?,?,?,?)", (str(uuid.uuid4()), "Review monthly expenses", "urgent", "q1"))

init_db()

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
    return {"status": "ok", "db": "postgres" if os.getenv("DATABASE_URL") else "sqlite"}

@app.get("/dashboard")
def dashboard():
    tasks = DB.execute(DB_PATH, "SELECT * FROM tasks ORDER BY created_at DESC", fetch=True) or []
    bills = DB.execute(DB_PATH, "SELECT * FROM bills ORDER BY created_at DESC", fetch=True) or []
    reminders = DB.execute(DB_PATH, "SELECT * FROM reminders WHERE done=0 ORDER BY remind_at ASC LIMIT 5", fetch=True) or []
    
    pending = sum(1 for t in tasks if not t["done"])
    completed = sum(1 for t in tasks if t["done"])
    overdue_bills = [b for b in bills if b["status"] == "overdue"]
    amount_due = sum(b["amount"] for b in bills if b["status"] in ("due","overdue"))
    
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"

    streak = 0
    for i in range(30):
        d = (date.today() - timedelta(days=i)).isoformat()
        row = DB.execute(DB_PATH, "SELECT tasks_done FROM daily_logs WHERE date=?", (d,), fetch=True)
        if row and row[0]["tasks_done"] > 0: streak += 1
        elif i > 0: break

    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    week_logs = DB.execute(DB_PATH, "SELECT * FROM daily_logs WHERE date >= ?", (week_start,), fetch=True) or []
    week_focus = sum(l["focus_minutes"] for l in week_logs)

    return {
        "greeting": greeting,
        "tasks": {"pending": pending, "completed": completed, "items": tasks},
        "bills": {"overdue": len(overdue_bills), "amount_due": amount_due, "items": bills},
        "reminders": {"count": len(reminders), "items": reminders},
        "productivity": {"streak": streak, "week_focus_minutes": week_focus}
    }

@app.get("/tasks")
def get_tasks():
    return {"tasks": DB.execute(DB_PATH, "SELECT * FROM tasks ORDER BY created_at DESC", fetch=True) or []}

@app.post("/tasks")
def add_task(t: TaskIn):
    tid = str(uuid.uuid4())
    DB.execute(DB_PATH, "INSERT INTO tasks (id,text,priority,quadrant,due) VALUES (?,?,?,?,?)", (tid, t.text, t.priority, t.quadrant, t.due))
    return {"id": tid}

@app.patch("/tasks/{tid}/toggle")
def toggle_task(tid: str):
    DB.execute(DB_PATH, "UPDATE tasks SET done = CASE WHEN done=1 THEN 0 ELSE 1 END WHERE id=?", (tid,))
    today = date.today().isoformat()
    # Update log logic simplified
    done_count = len(DB.execute(DB_PATH, "SELECT id FROM tasks WHERE done=1", fetch=True) or [])
    if DB.execute(DB_PATH, "SELECT id FROM daily_logs WHERE date=?", (today,), fetch=True):
        DB.execute(DB_PATH, "UPDATE daily_logs SET tasks_done=? WHERE date=?", (done_count, today))
    else:
        DB.execute(DB_PATH, "INSERT INTO daily_logs (id,date,tasks_done) VALUES (?,?,?)", (str(uuid.uuid4()), today, done_count))
    return {"status": "ok"}

@app.delete("/tasks/{tid}")
def delete_task(tid: str):
    DB.execute(DB_PATH, "DELETE FROM tasks WHERE id=?", (tid,))
    return {"status": "ok"}

@app.get("/bills")
def get_bills():
    return {"bills": DB.execute(DB_PATH, "SELECT * FROM bills ORDER BY created_at DESC", fetch=True) or []}

@app.post("/bills")
def add_bill(b: BillIn):
    bid = str(uuid.uuid4())
    DB.execute(DB_PATH, "INSERT INTO bills (id,name,amount,due,recurring) VALUES (?,?,?,?,?)", (bid, b.name, b.amount, b.due, b.recurring))
    return {"id": bid}

@app.patch("/bills/{bid}/pay")
def pay_bill(bid: str):
    DB.execute(DB_PATH, "UPDATE bills SET status='paid' WHERE id=?", (bid,))
    return {"status": "ok"}

@app.delete("/bills/{bid}")
def delete_bill(bid: str):
    DB.execute(DB_PATH, "DELETE FROM bills WHERE id=?", (bid,))
    return {"status": "ok"}

@app.get("/reminders")
def get_reminders():
    return {"reminders": DB.execute(DB_PATH, "SELECT * FROM reminders ORDER BY remind_at ASC", fetch=True) or []}

@app.post("/reminders")
def add_reminder(r: ReminderIn):
    rid = str(uuid.uuid4())
    DB.execute(DB_PATH, "INSERT INTO reminders (id,text,remind_at,repeat) VALUES (?,?,?,?)", (rid, r.text, r.remind_at, r.repeat))
    return {"id": rid}

@app.patch("/reminders/{rid}/done")
def done_reminder(rid: str):
    DB.execute(DB_PATH, "UPDATE reminders SET done=1 WHERE id=?", (rid,))
    return {"status": "ok"}

@app.delete("/reminders/{rid}")
def delete_reminder(rid: str):
    DB.execute(DB_PATH, "DELETE FROM reminders WHERE id=?", (rid,))
    return {"status": "ok"}

@app.get("/productivity/stats")
def get_prod_stats():
    logs = DB.execute(DB_PATH, "SELECT * FROM daily_logs ORDER BY date DESC LIMIT 30", fetch=True) or []
    total = len(DB.execute(DB_PATH, "SELECT id FROM tasks", fetch=True) or [])
    done = len(DB.execute(DB_PATH, "SELECT id FROM tasks WHERE done=1", fetch=True) or [])
    rate = round((done/total)*100) if total > 0 else 0
    return {"daily_logs": logs[::-1], "total_tasks": total, "done_tasks": done, "completion_rate": rate}

@app.post("/productivity/log")
def log_focus(l: DailyLogIn):
    existing = DB.execute(DB_PATH, "SELECT id, focus_minutes FROM daily_logs WHERE date=?", (l.date,), fetch=True)
    if existing:
        new_min = (existing[0]["focus_minutes"] or 0) + l.focus_minutes
        DB.execute(DB_PATH, "UPDATE daily_logs SET focus_minutes=?, notes=? WHERE date=?", (new_min, l.notes, l.date))
    else:
        DB.execute(DB_PATH, "INSERT INTO daily_logs (id,date,focus_minutes,notes) VALUES (?,?,?,?)", (str(uuid.uuid4()), l.date, l.focus_minutes, l.notes))
    return {"status": "ok"}

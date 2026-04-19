"""
Wellness Manager - FastAPI Backend
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

app = FastAPI(title="Wellness Manager API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wellness.db")

def init_db():
    queries = [
        "CREATE TABLE IF NOT EXISTS mood_logs (id TEXT PRIMARY KEY, score INTEGER NOT NULL, emoji TEXT DEFAULT '😊', notes TEXT DEFAULT '', logged_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS sleep_logs (id TEXT PRIMARY KEY, hours REAL NOT NULL, quality TEXT DEFAULT 'Good', bedtime TEXT DEFAULT '', logged_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS water_logs (id TEXT PRIMARY KEY, cups INTEGER DEFAULT 1, logged_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS journal_entries (id TEXT PRIMARY KEY, content TEXT NOT NULL, mood_tag TEXT DEFAULT 'Neutral', created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS exercises (id TEXT PRIMARY KEY, name TEXT NOT NULL, duration INTEGER NOT NULL, calories INTEGER DEFAULT 0, type TEXT DEFAULT 'Cardio', logged_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS habits (id TEXT PRIMARY KEY, name TEXT NOT NULL, icon TEXT DEFAULT '⭐', target_days INTEGER DEFAULT 7, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS habit_logs (id TEXT PRIMARY KEY, habit_id TEXT NOT NULL, done_date TEXT NOT NULL, UNIQUE(habit_id, done_date))"
    ]
    for q in queries:
        DB.execute(DB_PATH, q)

init_db()

# -- Models --
class MoodIn(BaseModel):
    score: int
    emoji: str = "😊"
    notes: str = ""

class SleepIn(BaseModel):
    hours: float
    quality: str = "Good"
    bedtime: str = ""

class WaterIn(BaseModel):
    cups: int = 1

class JournalIn(BaseModel):
    content: str
    mood_tag: str = "Neutral"

class ExerciseIn(BaseModel):
    name: str
    duration: int
    calories: int = 0
    type: str = "Cardio"

class HabitIn(BaseModel):
    name: str
    icon: str = "⭐"
    target_days: int = 7

# -- Routes --
@app.get("/health")
def health():
    return {"status": "ok", "db": "postgres" if os.getenv("DATABASE_URL") else "sqlite"}

@app.get("/dashboard")
def dashboard():
    today = date.today().isoformat()
    mood_logs = DB.execute(DB_PATH, "SELECT * FROM mood_logs WHERE logged_at >= ? ORDER BY logged_at DESC LIMIT 1", (today,), fetch=True) or []
    mood_today = mood_logs[0] if mood_logs else None
    
    sleep_logs = DB.execute(DB_PATH, "SELECT * FROM sleep_logs WHERE logged_at >= ? ORDER BY logged_at DESC LIMIT 1", (today,), fetch=True) or []
    sleep_today = sleep_logs[0] if sleep_logs else None
    
    water_res = DB.execute(DB_PATH, "SELECT SUM(cups) as total FROM water_logs WHERE logged_at >= ?", (today,), fetch=True)
    water_today = water_res[0]["total"] or 0 if water_res else 0
    
    exercise_res = DB.execute(DB_PATH, "SELECT SUM(duration) as dur, SUM(calories) as cal FROM exercises WHERE logged_at >= ?", (today,), fetch=True)
    exercise_today = exercise_res[0]["dur"] or 0 if exercise_res else 0
    calories_today = exercise_res[0]["cal"] or 0 if exercise_res else 0

    # Trend logic
    mood_trend = []
    sleep_trend = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        m_res = DB.execute(DB_PATH, "SELECT AVG(score) as avg_score FROM mood_logs WHERE logged_at >= ? AND logged_at < ?", (d, (date.today() - timedelta(days=i-1)).isoformat()), fetch=True)
        s_res = DB.execute(DB_PATH, "SELECT AVG(hours) as avg_hours FROM sleep_logs WHERE logged_at >= ? AND logged_at < ?", (d, (date.today() - timedelta(days=i-1)).isoformat()), fetch=True)
        mood_trend.append({"date": d, "score": round(m_res[0]["avg_score"] or 5, 1) if m_res else 5})
        sleep_trend.append({"date": d, "hours": round(s_res[0]["avg_hours"] or 0, 1) if s_res else 0})

    avg_res = DB.execute(DB_PATH, "SELECT AVG(score) as avg_mood, AVG(hours) as avg_sleep FROM mood_logs, sleep_logs WHERE mood_logs.logged_at >= CURRENT_DATE - INTERVAL '7 days'" if os.getenv("DATABASE_URL") else "SELECT AVG(score) as avg_mood, AVG(hours) as avg_sleep FROM mood_logs, sleep_logs WHERE mood_logs.logged_at >= date('now','-7 days')", fetch=True)
    
    avg_mood = avg_res[0]["avg_mood"] or 5 if avg_res else 5
    avg_sleep = avg_res[0]["avg_sleep"] or 7 if avg_res else 7
    burnout_risk = "Low" if avg_mood >= 7 else "Medium" if avg_mood >= 5 else "High"
    wellness_score = min(100, int(avg_mood * 10))

    habits = DB.execute(DB_PATH, "SELECT * FROM habits", fetch=True) or []
    habit_streaks = []
    for h in habits:
        streak = 0
        for i in range(30):
            d = (date.today() - timedelta(days=i)).isoformat()
            if DB.execute(DB_PATH, "SELECT id FROM habit_logs WHERE habit_id=? AND done_date=?", (h["id"], d), fetch=True):
                streak += 1
            elif i > 0: break
        done_today = DB.execute(DB_PATH, "SELECT id FROM habit_logs WHERE habit_id=? AND done_date=?", (h["id"], today), fetch=True) is not None
        habit_streaks.append({**h, "streak": streak, "done_today": done_today})

    return {
        "mood": {"score": mood_today["score"] if mood_today else None, "emoji": mood_today["emoji"] if mood_today else None},
        "sleep": {"hours": sleep_today["hours"] if sleep_today else None, "quality": sleep_today["quality"] if sleep_today else None},
        "water_today": water_today, "water_goal": 8, "exercise_today": exercise_today, "calories_today": calories_today,
        "burnout_risk": burnout_risk, "wellness_score": wellness_score, "avg_mood_7d": round(avg_mood, 1), "avg_sleep_7d": round(avg_sleep, 1),
        "mood_trend": mood_trend, "sleep_trend": sleep_trend, "habits": habit_streaks
    }

@app.post("/mood")
def log_mood(m: MoodIn):
    DB.execute(DB_PATH, "INSERT INTO mood_logs (id,score,emoji,notes) VALUES (?,?,?,?)", (str(uuid.uuid4()), m.score, m.emoji, m.notes))
    return {"status": "ok"}

@app.get("/mood/history")
def mood_history():
    return {"logs": DB.execute(DB_PATH, "SELECT * FROM mood_logs ORDER BY logged_at DESC LIMIT 30", fetch=True) or []}

@app.post("/sleep")
def log_sleep(s: SleepIn):
    DB.execute(DB_PATH, "INSERT INTO sleep_logs (id,hours,quality,bedtime) VALUES (?,?,?,?)", (str(uuid.uuid4()), s.hours, s.quality, s.bedtime))
    return {"status": "ok"}

@app.post("/water/log")
def log_water(w: WaterIn):
    DB.execute(DB_PATH, "INSERT INTO water_logs (id,cups) VALUES (?,?)", (str(uuid.uuid4()), w.cups))
    return {"status": "ok"}

@app.post("/journal")
def add_journal(j: JournalIn):
    DB.execute(DB_PATH, "INSERT INTO journal_entries (id,content,mood_tag) VALUES (?,?,?)", (str(uuid.uuid4()), j.content, j.mood_tag))
    return {"status": "ok"}

@app.get("/journal")
def get_journal():
    return {"entries": DB.execute(DB_PATH, "SELECT * FROM journal_entries ORDER BY created_at DESC LIMIT 20", fetch=True) or []}

@app.get("/burnout")
def burnout_check():
    # Simple workaround for date diffs
    res = DB.execute(DB_PATH, "SELECT AVG(score) as avg_mood, AVG(hours) as avg_sleep FROM mood_logs, sleep_logs", fetch=True)
    avg_mood = res[0]["avg_mood"] or 5 if res else 5
    avg_sleep = res[0]["avg_sleep"] or 7 if res else 7
    burnout_risk = "Low" if avg_mood >= 7 else "Medium" if avg_mood >= 5 else "High"
    tips = {"Low": ["Keep it up!"], "Medium": ["Take a break"], "High": ["Rest immediately"]}
    return {"burnout_risk": burnout_risk, "avg_mood_7d": round(avg_mood, 1), "avg_sleep_7d": round(avg_sleep, 1), "tips": tips[burnout_risk]}

@app.post("/exercise")
def log_exercise(e: ExerciseIn):
    DB.execute(DB_PATH, "INSERT INTO exercises (id,name,duration,calories,type) VALUES (?,?,?,?,?)", (str(uuid.uuid4()), e.name, e.duration, e.calories, e.type))
    return {"status": "ok"}

@app.get("/exercise/history")
def exercise_history():
    res = DB.execute(DB_PATH, "SELECT SUM(duration) as dur, SUM(calories) as cal FROM exercises", fetch=True)
    return {"exercises": DB.execute(DB_PATH, "SELECT * FROM exercises ORDER BY logged_at DESC LIMIT 30", fetch=True) or [], "week_minutes": res[0]["dur"] or 0, "week_calories": res[0]["cal"] or 0}

@app.get("/habits")
def get_habits():
    habits = DB.execute(DB_PATH, "SELECT * FROM habits", fetch=True) or []
    result = []
    today = date.today().isoformat()
    for h in habits:
        streak = 0
        for i in range(30):
            d = (date.today() - timedelta(days=i)).isoformat()
            if DB.execute(DB_PATH, "SELECT id FROM habit_logs WHERE habit_id=? AND done_date=?", (h["id"], d), fetch=True): streak += 1
            elif i > 0: break
        done_today = DB.execute(DB_PATH, "SELECT id FROM habit_logs WHERE habit_id=? AND done_date=?", (h["id"], today), fetch=True) is not None
        result.append({**h, "streak": streak, "done_today": done_today})
    return {"habits": result}

@app.post("/habits")
def add_habit(h: HabitIn):
    DB.execute(DB_PATH, "INSERT INTO habits (id,name,icon,target_days) VALUES (?,?,?,?)", (str(uuid.uuid4()), h.name, h.icon, h.target_days))
    return {"status": "ok"}

@app.post("/habits/{hid}/log")
def log_habit(hid: str):
    today = date.today().isoformat()
    if DB.execute(DB_PATH, "SELECT id FROM habit_logs WHERE habit_id=? AND done_date=?", (hid, today), fetch=True):
        DB.execute(DB_PATH, "DELETE FROM habit_logs WHERE habit_id=? AND done_date=?", (hid, today))
    else:
        DB.execute(DB_PATH, "INSERT INTO habit_logs (id,habit_id,done_date) VALUES (?,?,?)", (str(uuid.uuid4()), hid, today))
    return {"status": "ok"}

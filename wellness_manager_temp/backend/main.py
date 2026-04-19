"""
Wellness Manager - FastAPI Backend
Stack: FastAPI + SQLite
Features: Mood/Sleep/Water tracking, Exercise logs, Habit streaks, Burnout check
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

app = FastAPI(title="Wellness Manager API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wellness.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    # 1. Create tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS mood_logs (
            id TEXT PRIMARY KEY,
            score INTEGER NOT NULL,
            emoji TEXT DEFAULT '😊',
            notes TEXT DEFAULT '',
            logged_at TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS sleep_logs (
            id TEXT PRIMARY KEY,
            hours REAL NOT NULL,
            quality TEXT DEFAULT 'Good',
            bedtime TEXT DEFAULT '',
            logged_at TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS water_logs (
            id TEXT PRIMARY KEY,
            cups INTEGER DEFAULT 1,
            logged_at TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS journal_entries (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            mood_tag TEXT DEFAULT 'Neutral',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS exercises (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            duration INTEGER NOT NULL,
            calories INTEGER DEFAULT 0,
            type TEXT DEFAULT 'Cardio',
            logged_at TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS habits (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT DEFAULT '⭐',
            target_days INTEGER DEFAULT 7,
            created_at TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS habit_logs (
            id TEXT PRIMARY KEY,
            habit_id TEXT NOT NULL,
            done_date TEXT NOT NULL,
            UNIQUE(habit_id, done_date)
        );
    """)

    # 2. Migration
    tables_to_check = {
        "mood_logs": ["emoji", "notes", "logged_at"],
        "sleep_logs": ["quality", "bedtime", "logged_at"],
        "water_logs": ["cups", "logged_at"],
        "journal_entries": ["mood_tag", "created_at"],
        "exercises": ["duration", "calories", "type", "logged_at"],
        "habits": ["icon", "target_days", "created_at"]
    }
    for table, cols in tables_to_check.items():
        existing_cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        for col in cols:
            if col not in existing_cols:
                if col in ("logged_at", "created_at"):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
                elif col in ("score", "cups", "duration", "calories", "target_days"):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} INTEGER DEFAULT 0")
                else:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")

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

@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0"}

@app.get("/dashboard")
def dashboard():
    today = date.today().isoformat()
    with get_db() as db:
        mood_today = db.execute("SELECT * FROM mood_logs WHERE logged_at=? ORDER BY rowid DESC LIMIT 1", (today,)).fetchone()
        sleep_today = db.execute("SELECT * FROM sleep_logs WHERE logged_at=? ORDER BY rowid DESC LIMIT 1", (today,)).fetchone()
        water_today = db.execute("SELECT SUM(cups) FROM water_logs WHERE logged_at=?", (today,)).fetchone()[0] or 0
        exercise_today = db.execute("SELECT SUM(duration) FROM exercises WHERE logged_at=?", (today,)).fetchone()[0] or 0
        calories_today = db.execute("SELECT SUM(calories) FROM exercises WHERE logged_at=?", (today,)).fetchone()[0] or 0

        # 7-day trends
        mood_trend = []
        sleep_trend = []
        for i in range(6, -1, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            m = db.execute("SELECT AVG(score) FROM mood_logs WHERE logged_at=?", (d,)).fetchone()[0]
            s = db.execute("SELECT AVG(hours) FROM sleep_logs WHERE logged_at=?", (d,)).fetchone()[0]
            mood_trend.append({"date": d, "score": round(m or 5, 1)})
            sleep_trend.append({"date": d, "hours": round(s or 0, 1)})

        avg_mood = db.execute("SELECT AVG(score) FROM mood_logs WHERE logged_at >= date('now','-7 days')").fetchone()[0] or 5
        avg_sleep = db.execute("SELECT AVG(hours) FROM sleep_logs WHERE logged_at >= date('now','-7 days')").fetchone()[0] or 7
        burnout_risk = "Low" if avg_mood >= 7 else "Medium" if avg_mood >= 5 else "High"
        wellness_score = min(100, int(avg_mood * 10))

        # Habit streaks
        habits = [dict(r) for r in db.execute("SELECT * FROM habits").fetchall()]
        habit_streaks = []
        for h in habits:
            streak = 0
            for i in range(30):
                d = (date.today() - timedelta(days=i)).isoformat()
                row = db.execute("SELECT id FROM habit_logs WHERE habit_id=? AND done_date=?", (h["id"], d)).fetchone()
                if row:
                    streak += 1
                elif i > 0:
                    break
            done_today = db.execute("SELECT id FROM habit_logs WHERE habit_id=? AND done_date=?", (h["id"], today)).fetchone() is not None
            habit_streaks.append({**h, "streak": streak, "done_today": done_today})

        return {
            "mood": {"score": mood_today["score"] if mood_today else None, "emoji": mood_today["emoji"] if mood_today else None},
            "sleep": {"hours": sleep_today["hours"] if sleep_today else None, "quality": sleep_today["quality"] if sleep_today else None},
            "water_today": water_today,
            "water_goal": 8,
            "exercise_today": exercise_today,
            "calories_today": calories_today,
            "burnout_risk": burnout_risk,
            "wellness_score": wellness_score,
            "avg_mood_7d": round(avg_mood, 1),
            "avg_sleep_7d": round(avg_sleep, 1),
            "mood_trend": mood_trend,
            "sleep_trend": sleep_trend,
            "habits": habit_streaks
        }

@app.post("/mood")
def log_mood(m: MoodIn):
    with get_db() as db:
        db.execute("INSERT INTO mood_logs (id,score,emoji,notes) VALUES (?,?,?,?)",
                   (str(uuid.uuid4()), m.score, m.emoji, m.notes))
    return {"status": "logged"}

@app.get("/mood/history")
def mood_history():
    with get_db() as db:
        logs = [dict(r) for r in db.execute("SELECT * FROM mood_logs ORDER BY logged_at DESC LIMIT 30").fetchall()]
        return {"logs": logs}

@app.post("/sleep")
def log_sleep(s: SleepIn):
    with get_db() as db:
        db.execute("INSERT INTO sleep_logs (id,hours,quality,bedtime) VALUES (?,?,?,?)",
                   (str(uuid.uuid4()), s.hours, s.quality, s.bedtime))
    return {"status": "logged"}

@app.post("/water/log")
def log_water(w: WaterIn):
    with get_db() as db:
        db.execute("INSERT INTO water_logs (id,cups) VALUES (?,?)", (str(uuid.uuid4()), w.cups))
    return {"status": "logged"}

@app.post("/journal")
def add_journal(j: JournalIn):
    with get_db() as db:
        db.execute("INSERT INTO journal_entries (id,content,mood_tag) VALUES (?,?,?)",
                   (str(uuid.uuid4()), j.content, j.mood_tag))
    return {"status": "saved"}

@app.get("/journal")
def get_journal():
    with get_db() as db:
        entries = [dict(r) for r in db.execute("SELECT * FROM journal_entries ORDER BY created_at DESC LIMIT 20").fetchall()]
        return {"entries": entries}

@app.get("/burnout")
def burnout_check():
    with get_db() as db:
        avg_mood = db.execute("SELECT AVG(score) FROM mood_logs WHERE logged_at >= date('now','-7 days')").fetchone()[0] or 5
        avg_sleep = db.execute("SELECT AVG(hours) FROM sleep_logs WHERE logged_at >= date('now','-7 days')").fetchone()[0] or 7
        burnout_risk = "Low" if avg_mood >= 7 else "Medium" if avg_mood >= 5 else "High"
        tips = {
            "Low": ["Keep up the great work!", "Stay consistent with your wellness routine."],
            "Medium": ["Take short breaks during work", "Prioritize 7-8 hours of sleep", "Try a 10-minute walk"],
            "High": ["Take a full rest day", "Talk to someone you trust", "Disconnect from screens for 1 hour"]
        }
    return {"burnout_risk": burnout_risk, "avg_mood_7d": round(avg_mood, 1), "avg_sleep_7d": round(avg_sleep, 1), "tips": tips[burnout_risk]}

# -- Exercise --
@app.post("/exercise")
def log_exercise(e: ExerciseIn):
    with get_db() as db:
        eid = str(uuid.uuid4())
        db.execute("INSERT INTO exercises (id,name,duration,calories,type) VALUES (?,?,?,?,?)",
                   (eid, e.name, e.duration, e.calories, e.type))
        return {"id": eid, "status": "logged"}

@app.get("/exercise/history")
def exercise_history():
    with get_db() as db:
        exercises = [dict(r) for r in db.execute("SELECT * FROM exercises ORDER BY logged_at DESC LIMIT 30").fetchall()]
        total_minutes = db.execute("SELECT SUM(duration) FROM exercises WHERE logged_at >= date('now','-7 days')").fetchone()[0] or 0
        total_calories = db.execute("SELECT SUM(calories) FROM exercises WHERE logged_at >= date('now','-7 days')").fetchone()[0] or 0
        return {"exercises": exercises, "week_minutes": total_minutes, "week_calories": total_calories}

# -- Habits --
@app.get("/habits")
def get_habits():
    with get_db() as db:
        habits = [dict(r) for r in db.execute("SELECT * FROM habits ORDER BY created_at DESC").fetchall()]
        today = date.today().isoformat()
        result = []
        for h in habits:
            streak = 0
            for i in range(30):
                d = (date.today() - timedelta(days=i)).isoformat()
                row = db.execute("SELECT id FROM habit_logs WHERE habit_id=? AND done_date=?", (h["id"], d)).fetchone()
                if row:
                    streak += 1
                elif i > 0:
                    break
            done_today = db.execute("SELECT id FROM habit_logs WHERE habit_id=? AND done_date=?", (h["id"], today)).fetchone() is not None
            # 7-day history
            history = []
            for i in range(6, -1, -1):
                d = (date.today() - timedelta(days=i)).isoformat()
                row = db.execute("SELECT id FROM habit_logs WHERE habit_id=? AND done_date=?", (h["id"], d)).fetchone()
                history.append({"date": d, "done": row is not None})
            result.append({**h, "streak": streak, "done_today": done_today, "history": history})
        return {"habits": result}

@app.post("/habits")
def add_habit(h: HabitIn):
    with get_db() as db:
        hid = str(uuid.uuid4())
        db.execute("INSERT INTO habits (id,name,icon,target_days) VALUES (?,?,?,?)",
                   (hid, h.name, h.icon, h.target_days))
        return {"id": hid, "status": "created"}

@app.post("/habits/{hid}/log")
def log_habit(hid: str):
    today = date.today().isoformat()
    with get_db() as db:
        existing = db.execute("SELECT id FROM habit_logs WHERE habit_id=? AND done_date=?", (hid, today)).fetchone()
        if existing:
            db.execute("DELETE FROM habit_logs WHERE habit_id=? AND done_date=?", (hid, today))
            return {"status": "unmarked"}
        db.execute("INSERT INTO habit_logs (id,habit_id,done_date) VALUES (?,?,?)", (str(uuid.uuid4()), hid, today))
        return {"status": "logged"}

@app.delete("/habits/{hid}")
def delete_habit(hid: str):
    with get_db() as db:
        db.execute("DELETE FROM habits WHERE id=?", (hid,))
        db.execute("DELETE FROM habit_logs WHERE habit_id=?", (hid,))
        return {"status": "deleted"}

"""
Content Manager - FastAPI Backend
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

app = FastAPI(title="Content Manager API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content.db")

def init_db():
    queries = [
        "CREATE TABLE IF NOT EXISTS content_queue (id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT DEFAULT '', platform TEXT NOT NULL, status TEXT DEFAULT 'draft', tone TEXT DEFAULT 'Professional', tags TEXT DEFAULT '', scheduled_at TEXT DEFAULT '', published_at TEXT DEFAULT '', views INTEGER DEFAULT 0, likes INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS ideas (id TEXT PRIMARY KEY, title TEXT NOT NULL, notes TEXT DEFAULT '', platform TEXT DEFAULT 'LinkedIn', priority TEXT DEFAULT 'medium', created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS platform_stats (id TEXT PRIMARY KEY, platform TEXT NOT NULL, followers INTEGER DEFAULT 0, posts INTEGER DEFAULT 0, total_views INTEGER DEFAULT 0, total_likes INTEGER DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    ]
    for q in queries:
        DB.execute(DB_PATH, q)

init_db()

# -- Models --
class ContentIn(BaseModel):
    title: str
    body: str = ""
    platform: str = "LinkedIn"
    tone: str = "Professional"
    tags: str = ""
    scheduled_at: str = ""

class ContentUpdateIn(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    status: Optional[str] = None
    scheduled_at: Optional[str] = None
    views: Optional[int] = None
    likes: Optional[int] = None

class IdeaIn(BaseModel):
    title: str
    notes: str = ""
    platform: str = "LinkedIn"
    priority: str = "medium"

# -- Routes --
@app.get("/health")
def health():
    return {"status": "ok", "db": "postgres" if os.getenv("DATABASE_URL") else "sqlite"}

@app.get("/dashboard")
def dashboard():
    queue = DB.execute(DB_PATH, "SELECT * FROM content_queue ORDER BY created_at DESC", fetch=True) or []
    stats = DB.execute(DB_PATH, "SELECT * FROM platform_stats ORDER BY followers DESC", fetch=True) or []
    ideas = DB.execute(DB_PATH, "SELECT * FROM ideas ORDER BY created_at DESC LIMIT 5", fetch=True) or []

    # Total reach
    total_views = sum(s.get("total_views") or 0 for s in stats)
    total_followers = sum(s.get("followers") or 0 for s in stats)

    return {
        "queue": queue,
        "platform_stats": stats,
        "ideas": ideas,
        "total_views": total_views,
        "total_followers": total_followers
    }

@app.get("/queue")
def get_queue(status: Optional[str] = None, platform: Optional[str] = None):
    query = "SELECT * FROM content_queue"
    conditions = []
    params = []
    if status:
        conditions.append("status=?")
        params.append(status)
    if platform:
        conditions.append("platform=?")
        params.append(platform)
    if conditions: query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC"
    return {"items": DB.execute(DB_PATH, query, params, fetch=True) or []}

@app.post("/queue")
def add_to_queue(c: ContentIn):
    qid = str(uuid.uuid4())
    DB.execute(DB_PATH, "INSERT INTO content_queue (id,title,body,platform,tone,tags,scheduled_at) VALUES (?,?,?,?,?,?,?)", (qid, c.title, c.body, c.platform, c.tone, c.tags, c.scheduled_at))
    return {"id": qid}

@app.patch("/queue/{qid}")
def update_content(qid: str, u: ContentUpdateIn):
    updates = {}
    if u.title is not None: updates["title"] = u.title
    if u.body is not None: updates["body"] = u.body
    if u.status is not None:
        updates["status"] = u.status
        if u.status == "published": updates["published_at"] = datetime.now().isoformat()
    if u.scheduled_at is not None: updates["scheduled_at"] = u.scheduled_at
    if u.views is not None: updates["views"] = u.views
    if u.likes is not None: updates["likes"] = u.likes
    if not updates: return {"status": "no changes"}
    
    set_clause = ", ".join(f"{k}=?" for k in updates)
    DB.execute(DB_PATH, f"UPDATE content_queue SET {set_clause} WHERE id=?", list(updates.values()) + [qid])
    return {"status": "ok"}

@app.delete("/queue/{qid}")
def delete_from_queue(qid: str):
    DB.execute(DB_PATH, "DELETE FROM content_queue WHERE id=?", (qid,))
    return {"status": "ok"}

@app.get("/ideas")
def get_ideas():
    return {"ideas": DB.execute(DB_PATH, "SELECT * FROM ideas ORDER BY priority DESC, created_at DESC", fetch=True) or []}

@app.post("/ideas")
def add_idea(i: IdeaIn):
    iid = str(uuid.uuid4())
    DB.execute(DB_PATH, "INSERT INTO ideas (id,title,notes,platform,priority) VALUES (?,?,?,?,?)", (iid, i.title, i.notes, i.platform, i.priority))
    return {"id": iid}

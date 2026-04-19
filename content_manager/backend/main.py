"""
Content Manager - FastAPI Backend
Stack: FastAPI + SQLite
Features: Content Calendar, Publishing Queue with status tracking, Platform stats
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

app = FastAPI(title="Content Manager API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    # 1. Create tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS content_queue (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT DEFAULT '',
            platform TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            tone TEXT DEFAULT 'Professional',
            tags TEXT DEFAULT '',
            scheduled_at TEXT DEFAULT '',
            published_at TEXT DEFAULT '',
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS ideas (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            notes TEXT DEFAULT '',
            platform TEXT DEFAULT 'LinkedIn',
            priority TEXT DEFAULT 'medium',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS platform_stats (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            followers INTEGER DEFAULT 0,
            posts INTEGER DEFAULT 0,
            total_views INTEGER DEFAULT 0,
            total_likes INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # 2. Migration
    tables_to_check = {
        "content_queue": ["body", "status", "tone", "tags", "scheduled_at", "published_at", "views", "likes", "created_at"],
        "ideas": ["notes", "platform", "priority", "created_at"],
        "platform_stats": ["followers", "posts", "total_views", "total_likes", "updated_at"]
    }
    for table, cols in tables_to_check.items():
        existing_cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        for col in cols:
            if col not in existing_cols:
                if col in ("created_at", "updated_at"):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
                elif col in ("views", "likes", "followers", "posts", "total_views", "total_likes"):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} INTEGER DEFAULT 0")
                else:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")

    if conn.execute("SELECT COUNT(*) FROM content_queue").fetchone()[0] == 0:
        conn.executemany("INSERT INTO content_queue (id,title,platform,status,views,likes,tags) VALUES (?,?,?,?,?,?,?)", [
            (str(uuid.uuid4()), "5 AI Tools That Changed My Workflow", "LinkedIn", "published", 1240, 87, "AI,Productivity"),
            (str(uuid.uuid4()), "Local AI Stack — Complete Guide", "Twitter", "published", 3200, 210, "AI,Tech"),
            (str(uuid.uuid4()), "Gemini API Tutorial", "YouTube", "draft", 0, 0, "Tutorial,AI"),
            (str(uuid.uuid4()), "Morning Routine for Developers", "Instagram", "scheduled", 0, 0, "Lifestyle"),
        ])
    if conn.execute("SELECT COUNT(*) FROM ideas").fetchone()[0] == 0:
        conn.executemany("INSERT INTO ideas (id,title,platform,priority) VALUES (?,?,?,?)", [
            (str(uuid.uuid4()), "How I use Notion as a second brain", "LinkedIn", "high"),
            (str(uuid.uuid4()), "Top 10 VSCode extensions 2026", "Twitter", "medium"),
            (str(uuid.uuid4()), "Building a habit tracker from scratch", "YouTube", "low"),
        ])
    if conn.execute("SELECT COUNT(*) FROM platform_stats").fetchone()[0] == 0:
        conn.executemany("INSERT INTO platform_stats (id,platform,followers,posts,total_views,total_likes) VALUES (?,?,?,?,?,?)", [
            (str(uuid.uuid4()), "LinkedIn", 4800, 42, 28000, 1800),
            (str(uuid.uuid4()), "Twitter", 2100, 310, 95000, 5600),
            (str(uuid.uuid4()), "YouTube", 890, 18, 42000, 3200),
            (str(uuid.uuid4()), "Instagram", 1500, 85, 62000, 4100),
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

PLATFORMS = ["LinkedIn", "Twitter", "YouTube", "Instagram"]
STATUSES = ["draft", "scheduled", "published", "archived"]

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

class PlatformStatsIn(BaseModel):
    platform: str
    followers: int
    posts: int
    total_views: int = 0
    total_likes: int = 0

@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0"}

@app.get("/dashboard")
def dashboard():
    with get_db() as db:
        queue = [dict(r) for r in db.execute("SELECT * FROM content_queue ORDER BY created_at DESC").fetchall()]
        stats = [dict(r) for r in db.execute("SELECT * FROM platform_stats ORDER BY followers DESC").fetchall()]
        ideas = [dict(r) for r in db.execute("SELECT * FROM ideas ORDER BY created_at DESC LIMIT 5").fetchall()]

        # Status breakdown
        status_counts = {s: 0 for s in STATUSES}
        for item in queue:
            if item["status"] in status_counts:
                status_counts[item["status"]] += 1

        # Platform breakdown
        platform_counts = {}
        for item in queue:
            platform_counts[item["platform"]] = platform_counts.get(item["platform"], 0) + 1

        # Top performing content
        top_content = sorted([q for q in queue if q["status"] == "published"], key=lambda x: x["views"], reverse=True)[:3]

        # Total reach
        total_views = sum(s["total_views"] for s in stats)
        total_followers = sum(s["followers"] for s in stats)

        # Scheduled this week
        week_end = (date.today() + timedelta(days=7)).isoformat()
        today_str = date.today().isoformat()
        upcoming = [q for q in queue if q["status"] == "scheduled" and q["scheduled_at"] and today_str <= q["scheduled_at"][:10] <= week_end]

        return {
            "queue": queue,
            "status_counts": status_counts,
            "platform_counts": platform_counts,
            "platform_stats": stats,
            "ideas": ideas,
            "top_content": top_content,
            "total_views": total_views,
            "total_followers": total_followers,
            "upcoming_scheduled": len(upcoming),
            "upcoming_items": upcoming
        }

@app.get("/queue")
def get_queue(status: Optional[str] = None, platform: Optional[str] = None):
    with get_db() as db:
        query = "SELECT * FROM content_queue"
        conditions = []
        params = []
        if status:
            conditions.append("status=?")
            params.append(status)
        if platform:
            conditions.append("platform=?")
            params.append(platform)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        items = [dict(r) for r in db.execute(query, params).fetchall()]
        return {"items": items}

@app.post("/queue")
def add_to_queue(c: ContentIn):
    with get_db() as db:
        qid = str(uuid.uuid4())
        db.execute("INSERT INTO content_queue (id,title,body,platform,tone,tags,scheduled_at) VALUES (?,?,?,?,?,?,?)",
                   (qid, c.title, c.body, c.platform, c.tone, c.tags, c.scheduled_at))
        return {"id": qid, "status": "queued"}

@app.patch("/queue/{qid}")
def update_content(qid: str, u: ContentUpdateIn):
    with get_db() as db:
        updates = {}
        if u.title is not None: updates["title"] = u.title
        if u.body is not None: updates["body"] = u.body
        if u.status is not None:
            updates["status"] = u.status
            if u.status == "published":
                updates["published_at"] = datetime.now().isoformat()
        if u.scheduled_at is not None: updates["scheduled_at"] = u.scheduled_at
        if u.views is not None: updates["views"] = u.views
        if u.likes is not None: updates["likes"] = u.likes
        if not updates:
            return {"status": "no changes"}
        set_clause = ", ".join(f"{k}=?" for k in updates)
        db.execute(f"UPDATE content_queue SET {set_clause} WHERE id=?", list(updates.values()) + [qid])
        return {"status": "updated"}

@app.patch("/queue/{qid}/publish")
def publish_content(qid: str):
    with get_db() as db:
        db.execute("UPDATE content_queue SET status='published', published_at=? WHERE id=?",
                   (datetime.now().isoformat(), qid))
        return {"status": "published"}

@app.delete("/queue/{qid}")
def delete_from_queue(qid: str):
    with get_db() as db:
        db.execute("DELETE FROM content_queue WHERE id=?", (qid,))
        return {"status": "deleted"}

# -- Ideas Board --
@app.get("/ideas")
def get_ideas():
    with get_db() as db:
        ideas = [dict(r) for r in db.execute("SELECT * FROM ideas ORDER BY priority DESC, created_at DESC").fetchall()]
        return {"ideas": ideas}

@app.post("/ideas")
def add_idea(i: IdeaIn):
    with get_db() as db:
        iid = str(uuid.uuid4())
        db.execute("INSERT INTO ideas (id,title,notes,platform,priority) VALUES (?,?,?,?,?)",
                   (iid, i.title, i.notes, i.platform, i.priority))
        return {"id": iid, "status": "created"}

@app.patch("/ideas/{iid}/promote")
def promote_idea_to_queue(iid: str):
    """Convert an idea directly into a draft in the queue"""
    with get_db() as db:
        idea = db.execute("SELECT * FROM ideas WHERE id=?", (iid,)).fetchone()
        if not idea:
            raise HTTPException(status_code=404, detail="Idea not found")
        qid = str(uuid.uuid4())
        db.execute("INSERT INTO content_queue (id,title,body,platform) VALUES (?,?,?,?)",
                   (qid, idea["title"], idea["notes"], idea["platform"]))
        db.execute("DELETE FROM ideas WHERE id=?", (iid,))
        return {"id": qid, "status": "promoted to queue"}

@app.delete("/ideas/{iid}")
def delete_idea(iid: str):
    with get_db() as db:
        db.execute("DELETE FROM ideas WHERE id=?", (iid,))
        return {"status": "deleted"}

# -- Platform Stats --
@app.get("/stats")
def get_stats():
    with get_db() as db:
        stats = [dict(r) for r in db.execute("SELECT * FROM platform_stats ORDER BY followers DESC").fetchall()]
        return {"stats": stats}

@app.post("/stats")
def update_stats(s: PlatformStatsIn):
    with get_db() as db:
        existing = db.execute("SELECT id FROM platform_stats WHERE platform=?", (s.platform,)).fetchone()
        if existing:
            db.execute("UPDATE platform_stats SET followers=?, posts=?, total_views=?, total_likes=?, updated_at=? WHERE platform=?",
                       (s.followers, s.posts, s.total_views, s.total_likes, datetime.now().isoformat(), s.platform))
            return {"status": "updated"}
        sid = str(uuid.uuid4())
        db.execute("INSERT INTO platform_stats (id,platform,followers,posts,total_views,total_likes) VALUES (?,?,?,?,?,?)",
                   (sid, s.platform, s.followers, s.posts, s.total_views, s.total_likes))
        return {"id": sid, "status": "created"}

# -- Calendar --
@app.get("/calendar")
def content_calendar():
    """Returns scheduled/published content for the next 30 days"""
    with get_db() as db:
        today = date.today().isoformat()
        end = (date.today() + timedelta(days=30)).isoformat()
        items = [dict(r) for r in db.execute(
            "SELECT * FROM content_queue WHERE (scheduled_at BETWEEN ? AND ?) OR (status='published' AND published_at BETWEEN ? AND ?) ORDER BY scheduled_at ASC",
            (today, end + "T23:59:59", today, end + "T23:59:59")).fetchall()]
        return {"calendar": items, "from": today, "to": end}

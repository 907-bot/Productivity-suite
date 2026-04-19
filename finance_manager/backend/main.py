"""
Finance Manager - FastAPI Backend
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

# Add root to path to import db_helper
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from db_helper import DB

load_dotenv()

app = FastAPI(title="Finance Manager API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance.db")

def init_db():
    queries = [
        "CREATE TABLE IF NOT EXISTS transactions (id TEXT PRIMARY KEY, merchant TEXT NOT NULL, amount REAL NOT NULL, type TEXT DEFAULT 'debit', category TEXT DEFAULT 'Other', notes TEXT DEFAULT '', date TEXT DEFAULT CURRENT_DATE, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS goals (id TEXT PRIMARY KEY, name TEXT NOT NULL, target REAL NOT NULL, saved REAL DEFAULT 0, deadline TEXT DEFAULT '', icon TEXT DEFAULT '🎯', created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS budgets (id TEXT PRIMARY KEY, category TEXT NOT NULL UNIQUE, limit_amount REAL NOT NULL, month TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    ]
    for q in queries:
        DB.execute(DB_PATH, q)
    
    if not DB.execute(DB_PATH, "SELECT id FROM transactions LIMIT 1", fetch=True):
        DB.execute(DB_PATH, "INSERT INTO transactions (id,merchant,amount,type,category) VALUES (?,?,?,?,?)", (str(uuid.uuid4()), "Salary", 50000, "credit", "Income"))

init_db()

# -- Models --
class TransactionIn(BaseModel):
    merchant: str
    amount: float
    type: str = "debit"
    category: str = "Other"
    notes: str = ""
    date: Optional[str] = None

class GoalIn(BaseModel):
    name: str
    target: float
    saved: float = 0
    deadline: str = ""
    icon: str = "🎯"

class GoalSaveIn(BaseModel):
    amount: float

class BudgetIn(BaseModel):
    category: str
    limit_amount: float

# -- Routes --
@app.get("/health")
def health():
    return {"status": "ok", "db": "postgres" if os.getenv("DATABASE_URL") else "sqlite"}

@app.get("/dashboard")
def dashboard():
    month = date.today().strftime("%Y-%m")
    inc_res = DB.execute(DB_PATH, "SELECT SUM(amount) as inc FROM transactions WHERE type='credit' AND date LIKE ?", (f"{month}%",), fetch=True)
    income = inc_res[0]["inc"] or 0 if inc_res else 0
    
    exp_res = DB.execute(DB_PATH, "SELECT SUM(amount) as exp FROM transactions WHERE type='debit' AND date LIKE ?", (f"{month}%",), fetch=True)
    spent = exp_res[0]["exp"] or 0 if exp_res else 0
    
    goals = DB.execute(DB_PATH, "SELECT * FROM goals ORDER BY created_at DESC", fetch=True) or []
    recent = DB.execute(DB_PATH, "SELECT * FROM transactions ORDER BY created_at DESC LIMIT 5", fetch=True) or []
    
    budgets = DB.execute(DB_PATH, "SELECT * FROM budgets WHERE month=?", (month,), fetch=True) or []
    budget_status = []
    for b in budgets:
        spent_res = DB.execute(DB_PATH, "SELECT SUM(amount) as total FROM transactions WHERE category=? AND type='debit' AND date LIKE ?", (b["category"], f"{month}%"), fetch=True)
        spent_cat = spent_res[0]["total"] or 0 if spent_res else 0
        budget_status.append({**b, "spent": spent_cat, "remaining": b["limit_amount"] - spent_cat, "pct": min(100, int(spent_cat / b["limit_amount"] * 100)) if b["limit_amount"] > 0 else 0})

    for g in goals:
        g["pct"] = min(100, int((g["saved"] / g["target"]) * 100)) if g["target"] > 0 else 0

    return {
        "balance": income - spent, "income_this_month": income, "spent_this_month": spent,
        "goals": goals, "recent_transactions": recent, "budget_status": budget_status
    }

@app.get("/transactions")
def get_transactions(limit: int = 50):
    return {"transactions": DB.execute(DB_PATH, "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?", (limit,), fetch=True) or []}

@app.post("/transactions")
def add_transaction(t: TransactionIn):
    tid = str(uuid.uuid4())
    tx_date = t.date or date.today().isoformat()
    DB.execute(DB_PATH, "INSERT INTO transactions (id,merchant,amount,type,category,notes,date) VALUES (?,?,?,?,?,?,?)", (tid, t.merchant, t.amount, t.type, t.category, t.notes, tx_date))
    return {"id": tid}

@app.delete("/transactions/{tid}")
def delete_transaction(tid: str):
    DB.execute(DB_PATH, "DELETE FROM transactions WHERE id=?", (tid,))
    return {"status": "ok"}

@app.get("/goals")
def get_goals():
    goals = DB.execute(DB_PATH, "SELECT * FROM goals ORDER BY created_at DESC", fetch=True) or []
    for g in goals: g["pct"] = min(100, int((g["saved"] / g["target"]) * 100)) if g["target"] > 0 else 0
    return {"goals": goals}

@app.post("/goals")
def add_goal(g: GoalIn):
    gid = str(uuid.uuid4())
    DB.execute(DB_PATH, "INSERT INTO goals (id,name,target,saved,deadline,icon) VALUES (?,?,?,?,?,?)", (gid, g.name, g.target, g.saved, g.deadline, g.icon))
    return {"id": gid}

@app.patch("/goals/{gid}/save")
def add_to_goal(gid: str, body: GoalSaveIn):
    DB.execute(DB_PATH, "UPDATE goals SET saved = LEAST(target, saved + ?)" if os.getenv("DATABASE_URL") else "UPDATE goals SET saved = MIN(target, saved + ?)", (body.amount, gid))
    return {"status": "ok"}

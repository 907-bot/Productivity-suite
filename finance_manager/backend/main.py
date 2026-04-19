"""
Finance Manager - FastAPI Backend
Stack: FastAPI + SQLite
Features: Transactions, Goals, Budget Categories with limits, Monthly stats, Savings tracker
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

app = FastAPI(title="Finance Manager API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    # 1. Create tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            merchant TEXT NOT NULL,
            amount REAL NOT NULL,
            type TEXT DEFAULT 'debit',
            category TEXT DEFAULT 'Other',
            notes TEXT DEFAULT '',
            date TEXT DEFAULT (date('now')),
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS goals (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            target REAL NOT NULL,
            saved REAL DEFAULT 0,
            deadline TEXT DEFAULT '',
            icon TEXT DEFAULT '🎯',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS budgets (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL UNIQUE,
            limit_amount REAL NOT NULL,
            month TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # 2. Migration
    tables_to_check = {
        "transactions": ["type", "category", "notes", "date", "created_at"],
        "goals": ["saved", "deadline", "icon", "created_at"],
        "budgets": ["category", "limit_amount", "month", "created_at"]
    }
    for table, cols in tables_to_check.items():
        existing_cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        for col in cols:
            if col not in existing_cols:
                if col == "created_at":
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN created_at TEXT")
                elif col in ("amount", "target", "saved", "limit_amount"):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} REAL DEFAULT 0")
                else:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")

    if conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0:
        conn.executemany("INSERT INTO transactions (id,merchant,amount,type,category) VALUES (?,?,?,?,?)", [
            (str(uuid.uuid4()), "Swiggy", 450, "debit", "Food"),
            (str(uuid.uuid4()), "Salary", 50000, "credit", "Income"),
            (str(uuid.uuid4()), "Netflix", 649, "debit", "Entertainment"),
            (str(uuid.uuid4()), "Uber", 320, "debit", "Transport"),
            (str(uuid.uuid4()), "Grocery", 2100, "debit", "Food"),
            (str(uuid.uuid4()), "Electricity", 2400, "debit", "Utilities"),
        ])
    if conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0] == 0:
        conn.executemany("INSERT INTO goals (id,name,target,saved,icon) VALUES (?,?,?,?,?)", [
            (str(uuid.uuid4()), "Emergency Fund", 100000, 45000, "🛡️"),
            (str(uuid.uuid4()), "Vacation - Goa", 30000, 12000, "✈️"),
            (str(uuid.uuid4()), "New Laptop", 80000, 25000, "💻"),
        ])
    if conn.execute("SELECT COUNT(*) FROM budgets").fetchone()[0] == 0:
        month = date.today().strftime("%Y-%m")
        conn.executemany("INSERT INTO budgets (id,category,limit_amount,month) VALUES (?,?,?,?)", [
            (str(uuid.uuid4()), "Food", 8000, month),
            (str(uuid.uuid4()), "Entertainment", 2000, month),
            (str(uuid.uuid4()), "Transport", 3000, month),
            (str(uuid.uuid4()), "Utilities", 5000, month),
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

@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0"}

@app.get("/dashboard")
def dashboard():
    with get_db() as db:
        month = date.today().strftime("%Y-%m")
        income = db.execute("SELECT SUM(amount) FROM transactions WHERE type='credit' AND date LIKE ?", (f"{month}%",)).fetchone()[0] or 0
        spent = db.execute("SELECT SUM(amount) FROM transactions WHERE type='debit' AND date LIKE ?", (f"{month}%",)).fetchone()[0] or 0
        goals = [dict(r) for r in db.execute("SELECT * FROM goals ORDER BY created_at DESC").fetchall()]
        recent = [dict(r) for r in db.execute("SELECT * FROM transactions ORDER BY created_at DESC LIMIT 5").fetchall()]

        # Budget status
        budgets = [dict(r) for r in db.execute("SELECT * FROM budgets WHERE month=?", (month,)).fetchall()]
        budget_status = []
        for b in budgets:
            spent_cat = db.execute("SELECT SUM(amount) FROM transactions WHERE category=? AND type='debit' AND date LIKE ?",
                                   (b["category"], f"{month}%")).fetchone()[0] or 0
            budget_status.append({**b, "spent": spent_cat, "remaining": b["limit_amount"] - spent_cat,
                                   "pct": min(100, int(spent_cat / b["limit_amount"] * 100)) if b["limit_amount"] > 0 else 0})

        # Savings rate
        savings_rate = round(((income - spent) / income * 100) if income > 0 else 0, 1)

        for g in goals:
            g["pct"] = min(100, int((g["saved"] / g["target"]) * 100)) if g["target"] > 0 else 0

        # Anomalies: transactions > 2x average debit
        all_debits = [dict(r) for r in db.execute("SELECT amount FROM transactions WHERE type='debit'").fetchall()]
        avg_debit = sum(d["amount"] for d in all_debits) / len(all_debits) if all_debits else 0
        anomalies = [dict(r) for r in db.execute(
            "SELECT * FROM transactions WHERE type='debit' AND amount > ? ORDER BY amount DESC LIMIT 3",
            (avg_debit * 2,)).fetchall()]

        return {
            "balance": income - spent,
            "income_this_month": income,
            "spent_this_month": spent,
            "savings_rate": savings_rate,
            "goals": goals,
            "recent_transactions": recent,
            "budget_status": budget_status,
            "anomalies": anomalies
        }

@app.get("/transactions")
def get_transactions(limit: int = 50):
    with get_db() as db:
        txns = [dict(r) for r in db.execute("SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()]
        return {"transactions": txns}

@app.post("/transactions")
def add_transaction(t: TransactionIn):
    with get_db() as db:
        tid = str(uuid.uuid4())
        tx_date = t.date or date.today().isoformat()
        db.execute("INSERT INTO transactions (id,merchant,amount,type,category,notes,date) VALUES (?,?,?,?,?,?,?)",
                   (tid, t.merchant, t.amount, t.type, t.category, t.notes, tx_date))
        return {"id": tid, "status": "created"}

@app.delete("/transactions/{tid}")
def delete_transaction(tid: str):
    with get_db() as db:
        db.execute("DELETE FROM transactions WHERE id=?", (tid,))
        return {"status": "deleted"}

@app.get("/goals")
def get_goals():
    with get_db() as db:
        goals = [dict(r) for r in db.execute("SELECT * FROM goals ORDER BY created_at DESC").fetchall()]
        for g in goals:
            g["pct"] = min(100, int((g["saved"] / g["target"]) * 100)) if g["target"] > 0 else 0
        return {"goals": goals}

@app.post("/goals")
def add_goal(g: GoalIn):
    with get_db() as db:
        gid = str(uuid.uuid4())
        db.execute("INSERT INTO goals (id,name,target,saved,deadline,icon) VALUES (?,?,?,?,?,?)",
                   (gid, g.name, g.target, g.saved, g.deadline, g.icon))
        return {"id": gid, "status": "created"}

@app.patch("/goals/{gid}/save")
def add_to_goal(gid: str, body: GoalSaveIn):
    with get_db() as db:
        db.execute("UPDATE goals SET saved = MIN(target, saved + ?) WHERE id=?", (body.amount, gid))
        return {"status": "updated"}

@app.delete("/goals/{gid}")
def delete_goal(gid: str):
    with get_db() as db:
        db.execute("DELETE FROM goals WHERE id=?", (gid,))
        return {"status": "deleted"}

@app.get("/spend/by-category")
def spend_by_category():
    with get_db() as db:
        month = date.today().strftime("%Y-%m")
        rows = db.execute("SELECT category, SUM(amount) as total FROM transactions WHERE type='debit' AND date LIKE ? GROUP BY category", (f"{month}%",)).fetchall()
        return {"categories": {r["category"]: r["total"] for r in rows}}

@app.get("/spend/monthly")
def monthly_spend():
    """Last 6 months spending trend"""
    with get_db() as db:
        result = []
        for i in range(5, -1, -1):
            d = date.today().replace(day=1) - timedelta(days=i*30)
            m = d.strftime("%Y-%m")
            income = db.execute("SELECT SUM(amount) FROM transactions WHERE type='credit' AND date LIKE ?", (f"{m}%",)).fetchone()[0] or 0
            spent = db.execute("SELECT SUM(amount) FROM transactions WHERE type='debit' AND date LIKE ?", (f"{m}%",)).fetchone()[0] or 0
            result.append({"month": m, "income": income, "spent": spent, "saved": income - spent})
        return {"monthly": result}

@app.get("/budgets")
def get_budgets():
    with get_db() as db:
        month = date.today().strftime("%Y-%m")
        budgets = [dict(r) for r in db.execute("SELECT * FROM budgets WHERE month=? ORDER BY category", (month,)).fetchall()]
        for b in budgets:
            spent = db.execute("SELECT SUM(amount) FROM transactions WHERE category=? AND type='debit' AND date LIKE ?",
                               (b["category"], f"{month}%")).fetchone()[0] or 0
            b["spent"] = spent
            b["remaining"] = b["limit_amount"] - spent
            b["pct"] = min(100, int(spent / b["limit_amount"] * 100)) if b["limit_amount"] > 0 else 0
        return {"budgets": budgets}

@app.post("/budgets")
def set_budget(b: BudgetIn):
    with get_db() as db:
        month = date.today().strftime("%Y-%m")
        existing = db.execute("SELECT id FROM budgets WHERE category=? AND month=?", (b.category, month)).fetchone()
        if existing:
            db.execute("UPDATE budgets SET limit_amount=? WHERE category=? AND month=?", (b.limit_amount, b.category, month))
            return {"status": "updated"}
        bid = str(uuid.uuid4())
        db.execute("INSERT INTO budgets (id,category,limit_amount,month) VALUES (?,?,?,?)", (bid, b.category, b.limit_amount, month))
        return {"id": bid, "status": "created"}

@app.get("/anomalies")
def detect_anomalies():
    with get_db() as db:
        all_debits = [dict(r) for r in db.execute("SELECT amount FROM transactions WHERE type='debit'").fetchall()]
        avg_debit = sum(d["amount"] for d in all_debits) / len(all_debits) if all_debits else 0
        txns = [dict(r) for r in db.execute(
            "SELECT * FROM transactions WHERE type='debit' AND amount > ? ORDER BY amount DESC LIMIT 5",
            (avg_debit * 2,)).fetchall()]
    anomalies = [{"transaction": t, "reason": f"High spend of ₹{t['amount']} at {t['merchant']} (avg: ₹{avg_debit:.0f})"} for t in txns]
    return {"anomalies": anomalies, "avg_transaction": round(avg_debit, 2)}

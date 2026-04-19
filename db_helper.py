import os
import sqlite3
import psycopg2
import uuid
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL")

class DB:
    @staticmethod
    @contextmanager
    def get_conn(db_path):
        if DATABASE_URL:
            # Use Supabase / Postgres
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = True
            try:
                yield conn
            finally:
                conn.close()
        else:
            # Use Local SQLite
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    @classmethod
    def execute(cls, db_path, query, params=(), fetch=False):
        # Convert SQLite '?' placeholder to Postgres '%s'
        if DATABASE_URL:
            query = query.replace('?', '%s')
        
        with cls.get_conn(db_path) as conn:
            if DATABASE_URL:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute(query, params)
                if fetch:
                    return [dict(r) for r in cur.fetchall()]
                return None
            else:
                cur = conn.execute(query, params)
                if fetch:
                    return [dict(r) for r in cur.fetchall()]
                return None

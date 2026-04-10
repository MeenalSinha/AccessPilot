"""
Database Layer — SQLite persistence via aiosqlite.
Ensures session data and task logs survive application restarts.
"""
import json
import logging
import os
import aiosqlite
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "accesspilot.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT,
                finished_at TEXT,
                is_running BOOLEAN,
                task_json TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp TEXT,
                action_json TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        """)
        await db.commit()
    logger.info(f"Database initialized at {DB_PATH}")

async def save_session(session_id: str, is_running: bool, task_data: dict, finished_at: datetime = None):
    async with aiosqlite.connect(DB_PATH) as db:
        created_at = datetime.now(timezone.utc).isoformat()
        finished_at_str = finished_at.isoformat() if finished_at else None
        
        await db.execute("""
            INSERT INTO sessions (session_id, created_at, finished_at, is_running, task_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                is_running = excluded.is_running,
                task_json = excluded.task_json,
                finished_at = excluded.finished_at
        """, (session_id, created_at, finished_at_str, is_running, json.dumps(task_data)))
        await db.commit()

async def log_action(session_id: str, action_data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        timestamp = datetime.now(timezone.utc).isoformat()
        await db.execute("""
            INSERT INTO action_logs (session_id, timestamp, action_json)
            VALUES (?, ?, ?)
        """, (session_id, timestamp, json.dumps(action_data)))
        await db.commit()

async def get_all_sessions():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sessions ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def delete_session(session_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM action_logs WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await db.commit()
